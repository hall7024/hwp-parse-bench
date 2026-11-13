"""ai-oss-support가 모은 후보(candidates.json)를 corpus/ 구조로 옮긴다. 한 번만 돌리는 스크립트.

사용: uv run python scripts/import_candidates.py <candidates.json>
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIR_MIN = 0.98
# 페이지에서 공공누리 고지를 찾지 못한 문서
NO_LICENSE = {"kr-156789037", "kr-156789038"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_similarity(text: str) -> float | None:
    m = re.search(r"유사도 ([0-9.]+)", text)
    return float(m.group(1)) if m else None


def main(src: str) -> None:
    candidates = json.loads(Path(src).read_text(encoding="utf-8"))
    out = []
    for c in candidates:
        if c["id"] in NO_LICENSE:
            continue
        is_law = c["id"].startswith("law")
        bundled = is_law
        base = ROOT / ("corpus/files" if bundled else "corpus/cache") / c["id"]
        files = {}
        for f in c["files"]:
            fmt = f["format"]
            if fmt in files:
                continue
            dest = base / f"doc.{fmt}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f["path"], dest)
            if sha256(dest) != f["sha256"]:
                raise SystemExit(f"해시 불일치: {c['id']} {fmt}")
            files[fmt] = {
                "path": str(dest.relative_to(ROOT)),
                "sha256": f["sha256"],
                "bytes": f["bytes"],
                "url": c["download"].get(fmt),
            }
        similarity = pair_similarity(c.get("hwp_hwpx_pair", ""))
        tests = []
        if "hwpx" in files:
            tests.append({"format": "hwpx", "track": "structure", "truth": "hwpx"})
            if "hwp" in files and similarity is not None and similarity >= PAIR_MIN:
                tests.append({"format": "hwp", "track": "structure", "truth": "hwpx"})
        elif "hwp" in files and "pdf" in files:
            tests.append({"format": "hwp", "track": "text", "truth": "pdf"})
        if not tests:
            continue
        title = c["title"] if is_law else c["title"]
        out.append(
            {
                "id": c["id"],
                "title": f"{c['law']} {title}" if is_law else title,
                "publisher": "법제처 국가법령정보센터" if is_law else c.get("ministry", ""),
                "date": c.get("date"),
                "source_page": c["source_page"],
                "license": "kr-copyright-art7" if is_law else "kogl-type1-text",
                "license_basis": c["license_basis"],
                "bundled": bundled,
                "pair_similarity": similarity,
                "files": files,
                "tests": tests,
                "tags": c.get("tags", []),
                "structure": c.get("structure"),
                "risks": c.get("risks", []),
            }
        )
    manifest = ROOT / "corpus/manifest.jsonl"
    manifest.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in out), encoding="utf-8")
    n_tests = sum(len(e["tests"]) for e in out)
    print(f"문서 {len(out)}개, 시험 {n_tests}건 → {manifest.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1])
