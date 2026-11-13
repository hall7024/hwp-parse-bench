"""지표: 텍스트 NID, 표 TEDS/TEDS-S, 제목 F1."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from apted import APTED, Config
from rapidfuzz.distance import Indel, Levenshtein
from scipy.optimize import linear_sum_assignment

from .model import Document, Table, normalize_text


def _nid(a: str, b: str) -> float:
    """opendataloader-bench의 NID: 1 - indel 거리 / (두 길이의 합)."""
    if not a and not b:
        return 1.0
    return Indel.normalized_similarity(a, b)


def text_nid(truth: Document, pred: Document) -> float:
    """표 칸을 포함한 전체 텍스트의 NID. 표를 못 알아보고 글로만 낸 파서도 같은 기준으로 잰다."""
    return _nid(truth.full_text(), pred.full_text())


def text_nid_s(truth: Document, pred: Document) -> float | None:
    """표 밖 본문만의 NID (NID-S). 정답 본문이 비어 있으면 None."""
    a = truth.body_text()
    return None if not a else _nid(a, pred.body_text())


def char_f1(truth_text: str, pred_text: str) -> tuple[float, float, float]:
    """순서와 무관한 글자 F1 (공백 제외). text 트랙(PDF 약한 정답)에 쓴다. (재현율, 정밀도, F1)"""
    t = Counter(c for c in normalize_text(truth_text) if not c.isspace())
    p = Counter(c for c in normalize_text(pred_text) if not c.isspace())
    if not t:
        return (1.0, 1.0, 1.0) if not p else (0.0, 0.0, 0.0)
    hit = sum((t & p).values())
    if hit == 0:
        return 0.0, 0.0, 0.0
    recall, precision = hit / sum(t.values()), hit / sum(p.values())
    return recall, precision, 2 * recall * precision / (recall + precision)


# --- TEDS ---


@dataclass
class _Node:
    tag: str
    colspan: int = 1
    rowspan: int = 1
    text: str = ""
    children: list[_Node] | None = None


def _tree(table: Table) -> tuple[_Node, int]:
    rows = [_Node("tr", children=[_Node("td", c.colspan, c.rowspan, normalize_text(c.text), []) for c in r]) for r in table.rows]
    # PubTabNet처럼 table 루트는 세지 않는다 (len(table.xpath(".//*")))
    size = len(rows) + sum(len(r.children or []) for r in rows)
    return _Node("table", children=rows), size


class _TedsConfig(Config):
    def __init__(self, structure_only: bool):
        self.structure_only = structure_only

    def rename(self, n1: _Node, n2: _Node) -> float:
        if n1.tag != n2.tag or n1.colspan != n2.colspan or n1.rowspan != n2.rowspan:
            return 1.0
        if n1.tag == "td" and not self.structure_only:
            if not n1.text and not n2.text:
                return 0.0
            return Levenshtein.normalized_distance(n1.text, n2.text)
        return 0.0

    def children(self, node: _Node) -> list[_Node]:
        return node.children or []


def teds(truth: Table, pred: Table, structure_only: bool = False) -> float:
    """Zhong et al. 2020의 TEDS. 칸 텍스트는 정규화 편집거리로 비교한다."""
    t1, n1 = _tree(truth)
    t2, n2 = _tree(pred)
    if max(n1, n2) == 0:
        return 1.0
    distance = APTED(t1, t2, _TedsConfig(structure_only)).compute_edit_distance()
    return max(0.0, 1.0 - distance / max(n1, n2))


@dataclass
class TableScore:
    teds: float | None
    teds_s: float | None
    truth_count: int
    pred_count: int


def _match(tt: list[Table], pt: list[Table], recall_only: bool) -> TableScore:
    if not tt:
        return TableScore(None, None, 0, len(pt))
    if not pt:
        return TableScore(0.0, 0.0, len(tt), 0)
    full = [[teds(t, p) for p in pt] for t in tt]
    rows, cols = linear_sum_assignment([[1 - s for s in r] for r in full])
    pairs = list(zip(rows, cols, strict=True))
    total = sum(full[r][c] for r, c in pairs)
    total_s = sum(teds(tt[r], pt[c], structure_only=True) for r, c in pairs)
    if recall_only:
        return TableScore(total / len(tt), total_s / len(tt), len(tt), len(pt))
    denom = len(tt) + len(pt)
    return TableScore(2 * total / denom, 2 * total_s / denom, len(tt), len(pt))


def table_score(truth: Document, pred: Document, subset: str = "all") -> TableScore:
    """정답 표와 출력 표를 TEDS가 최대가 되게 짝짓는다. 점수 = 2·Σ매칭 / (정답 수 + 출력 수).

    짝 없는 표(놓친 표, 쪼개지거나 지어낸 표)는 0점으로 들어간다. 정답에 해당 표가 없으면 None.
    subset:
      all     모든 표
      grid    2행 2열 이상인 표만 (양쪽 모두). 1행·1열 꾸밈 틀을 빼고 본다
      nomerge 병합 칸이 없는 격자 정답 표만. GFM처럼 병합을 표현 못 하는 출력의 공정 비교용.
              출력은 격자 표 전부와 짝을 찾고, 점수는 정답 표 기준 재현율이다
    """
    tt, pt = truth.tables(), pred.tables()
    if subset == "grid":
        return _match([t for t in tt if t.is_grid], [p for p in pt if p.is_grid], recall_only=False)
    if subset == "nomerge":
        return _match([t for t in tt if t.is_grid and not t.has_merged], [p for p in pt if p.is_grid], recall_only=True)
    return _match(tt, pt, recall_only=False)


# --- 제목 ---


def _f1(truth: Counter, pred: Counter) -> float:
    hit = sum((truth & pred).values())
    if hit == 0:
        return 0.0
    precision, recall = hit / sum(pred.values()), hit / sum(truth.values())
    return 2 * precision * recall / (precision + recall)


@dataclass
class HeadingScore:
    f1: float | None
    f1_level: float | None


def heading_score(truth: Document, pred: Document) -> HeadingScore:
    """제목 텍스트 F1과, 레벨까지 맞아야 하는 F1. 레벨은 각 문서의 가장 얕은 제목을 1로 맞춘 상대 레벨."""
    th, ph = truth.headings(), pred.headings()
    if not th:
        return HeadingScore(None, None)
    tbase = min(h.level for h in th)
    pbase = min((h.level for h in ph), default=1)
    text = _f1(Counter(normalize_text(h.text) for h in th), Counter(normalize_text(h.text) for h in ph))
    leveled = _f1(
        Counter((h.level - tbase, normalize_text(h.text)) for h in th),
        Counter((h.level - pbase, normalize_text(h.text)) for h in ph),
    )
    return HeadingScore(text, leveled)
