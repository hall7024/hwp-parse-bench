"""집계 → Markdown 순위표."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .corpus import ROOT

README = ROOT / "README.md"
BEGIN, END = "<!-- leaderboard:begin -->", "<!-- leaderboard:end -->"


def _f(v: float | None) -> str:
    return "–" if v is None else f"{v:.3f}"


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{v * 100:.0f}%"


def leaderboard(run_dir: Path) -> str:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    info = {a["name"]: a for a in meta["adapters"]}

    def key(item):
        # 표를 낼 수 있는 파서를 먼저, 그 안에서 NID와 TEDS 격자의 평균 순. 텍스트 전용은 NID 순으로 뒤에
        s = item[1]["structure_hwpx"]
        if s["teds_grid"] is None:
            return (1, -(s["nid"] or 0))
        return (0, -(s["nid"] + s["teds_grid"]) / 2)

    rows = sorted(summary.items(), key=key)
    n_hwpx = max((s["structure_hwpx"]["n"] for s in summary.values()), default=0)
    n_hwp = max((s["structure_hwp"]["n"] for s in summary.values()), default=0)
    n_text = max((s["text_hwp"]["n"] for s in summary.values()), default=0)
    lines = [
        f"실행 `{meta['run_id']}` · {meta['environment']['platform']} · 시험 {meta['tests']}건",
        "",
        "| 파서 | 버전 | NID | TEDS 격자 | TEDS-S 격자 | TEDS 병합 없는 표 | TEDS 모든 표 | HWP 짝 NID | HWP 짝 TEDS 격자 | HWP 글자 F1 | 실패 | 시간(중앙) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, s in rows:
        x, h, t = s["structure_hwpx"], s["structure_hwp"], s["text_hwp"]
        a = info.get(name, {})
        secs = "–" if s["median_seconds"] is None else f"{s['median_seconds']:.2f}s"
        lines.append(
            f"| {name} | {a.get('version', '')} | {_f(x['nid'])} | {_f(x['teds_grid'])} | {_f(x['teds_s_grid'])} "
            f"| {_f(x['teds_nomerge'])} | {_f(x['teds'])} | {_f(h['nid'])} | {_f(h['teds_grid'])} | {_f(t['char_f1'])} "
            f"| {_pct(s['failure_rate'])} | {secs} |"
        )
    lines += [
        "",
        f"- NID·TEDS 열: HWPX 원본 {n_hwpx}건. 정답은 원본 XML에서 독립 추출했다. HWP 짝 열: 같은 문서의 HWP {n_hwp}건(HWPX 정답 공유).",
        f"- HWP 글자 F1: 짝 HWPX가 없는 HWP {n_text}건(법령 별표 등). 한컴 PDF의 글과 순서 무관 글자 F1로 비교한 약한 정답이다.",
        "- TEDS 격자는 2행 2열 이상인 표만 본다. 보도자료 제목 상자 같은 1행·1열 꾸밈 틀을 글로 펴는 파서도 감점하지 않으려는 것이다. "
        "모든 표를 본 값은 TEDS 모든 표 열에 있다. TEDS 병합 없는 표는 GFM처럼 병합 칸을 표현하지 못하는 출력과 공정하게 비교하려는 값이다.",
        "- 정렬: NID와 TEDS 격자의 평균. 일반 텍스트만 내는 파서(표 지표 –)와 HWPX를 지원하지 않는 파서(pyhwp, llama-index)는 뒤에 둔다. pyhwp는 HWP 짝 열을 보면 된다. 실패(오류·시간 초과·빈 출력)는 0점으로 들어가고, 지원하지 않는 형식은 집계에서 뺀다. "
        "제목 F1은 v0.1 정답에 개요 스타일 제목이 없어 싣지 않았다.",
    ]
    return "\n".join(lines)


def write(run_dir: Path) -> str:
    table = leaderboard(run_dir)
    (run_dir / "report.md").write_text(table + "\n", encoding="utf-8")
    if README.exists():
        text = README.read_text(encoding="utf-8")
        if BEGIN in text and END in text:
            text = re.sub(f"{re.escape(BEGIN)}.*?{re.escape(END)}", f"{BEGIN}\n{table}\n{END}", text, flags=re.S)
            README.write_text(text, encoding="utf-8")
    return table
