"""실행 결과 채점과 집계."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from . import metrics, truth
from .corpus import tests
from .model import Document
from .normalize import from_markdown, from_plain_text
from .runner import Run, adapters

# 집계 표에 쓰는 지표 이름
STRUCTURE_METRICS = ("nid", "nid_s", "teds_grid", "teds_s_grid", "teds_nomerge", "teds", "teds_s", "heading_f1")
TEXT_METRICS = ("char_recall", "char_f1")


def _parse(output: str, kind: str):
    return from_markdown(output) if kind == "markdown" else from_plain_text(output)


def score_case(track: str, doc_id: str, output: str | None, kind: str) -> dict:
    """출력 하나의 점수. output이 None이면 실패(0점, 정답에 해당 요소가 없으면 None)."""
    if track == "text":
        if output is None:
            return {"char_recall": 0.0, "char_f1": 0.0}
        # Markdown·HTML 기호가 글자로 세어지지 않게 문서 모델을 거쳐 글만 비교한다
        r, _, f1 = metrics.char_f1(truth.load_text(doc_id), _parse(output, kind).full_text())
        return {"char_recall": r, "char_f1": f1}
    doc, status = truth.load_document(doc_id)
    # 실패는 빈 문서로 채점한다. 정답에 있는 요소의 점수는 모두 0이 된다
    p = _parse(output, kind) if output is not None else Document([])
    scores: dict = {"truth_status": status, "nid": metrics.text_nid(doc, p), "nid_s": metrics.text_nid_s(doc, p)}
    for subset, key in (("all", "teds"), ("grid", "teds_grid"), ("nomerge", "teds_nomerge")):
        ts = metrics.table_score(doc, p, subset)
        scores[key] = ts.teds
        if subset == "all":
            scores["teds_s"] = ts.teds_s
            scores["tables_truth"], scores["tables_pred"] = ts.truth_count, ts.pred_count
        elif subset == "grid":
            scores["teds_s_grid"] = ts.teds_s
    hs = metrics.heading_score(doc, p)
    scores["heading_f1"] = hs.f1
    scores["heading_f1_level"] = hs.f1_level
    if kind == "text":
        # 일반 텍스트만 내는 파서는 표·제목을 낼 수 없다. 0점이 아니라 "해당 없음"이다
        for key in ("nid_s", "teds", "teds_s", "teds_grid", "teds_s_grid", "teds_nomerge", "heading_f1", "heading_f1_level"):
            scores[key] = None
    return scores


def score_run(run_dir: Path, log=print) -> Path:
    registry = {a.name: a for a in adapters()}
    by_key = {t.key: t for t in tests()}
    runs = [Run(**json.loads(line)) for line in (run_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    out = run_dir / "scores.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in runs:
            if r.status == "unsupported":
                continue
            t = by_key[r.test]
            raw = run_dir / "raw" / r.adapter / f"{r.test}.out"
            output = raw.read_text(encoding="utf-8", errors="replace") if r.status == "ok" else None
            row = {**asdict(r), "doc": t.doc_id, "format": t.format, "track": t.track, "tags": list(t.tags)}
            try:
                row.update(score_case(t.track, t.doc_id, output, registry[r.adapter].output))
            except Exception as e:  # 채점 실패는 기록하고 계속
                row["score_error"] = f"{type(e).__name__}: {e}"
                log(f"채점 실패 {r.adapter} {r.test}: {row['score_error']}")
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out


def _mean(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


def summarize(run_dir: Path) -> dict:
    rows = [json.loads(line) for line in (run_dir / "scores.jsonl").read_text(encoding="utf-8").splitlines()]
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["adapter"]].append(r)
    summary: dict = {}
    for name, rs in groups.items():
        s: dict = {"cases": len(rs), "failures": sum(r["status"] != "ok" for r in rs)}
        s["failure_rate"] = s["failures"] / len(rs)
        secs = [r["seconds"] for r in rs if r["status"] == "ok" and r["seconds"] is not None]
        s["median_seconds"] = statistics.median(secs) if secs else None
        for fmt in ("hwpx", "hwp"):
            st = [r for r in rs if r["track"] == "structure" and r["format"] == fmt]
            s[f"structure_{fmt}"] = {m: _mean([r.get(m) for r in st]) for m in STRUCTURE_METRICS} | {"n": len(st)}
        rv = [r for r in rs if r["track"] == "structure" and r.get("truth_status") == "reviewed"]
        s["structure_reviewed"] = {m: _mean([r.get(m) for r in rv]) for m in STRUCTURE_METRICS} | {"n": len(rv)}
        tx = [r for r in rs if r["track"] == "text"]
        s["text_hwp"] = {m: _mean([r.get(m) for r in tx]) for m in TEXT_METRICS} | {"n": len(tx)}
        tags: dict[str, list[dict]] = defaultdict(list)
        for r in rs:
            if r["track"] == "structure":
                for tag in r["tags"]:
                    tags[tag].append(r)
        s["by_tag"] = {
            tag: {"n": len(v), "nid": _mean([r.get("nid") for r in v]), "teds": _mean([r.get("teds") for r in v])}
            for tag, v in sorted(tags.items())
        }
        summary[name] = s
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return summary
