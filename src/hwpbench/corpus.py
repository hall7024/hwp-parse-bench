"""코퍼스 manifest 읽기와 내려받기."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "corpus" / "manifest.jsonl"
MAX_DOWNLOAD = 50 * 1024 * 1024
REQUEST_INTERVAL = 1.0


@dataclass(frozen=True)
class Case:
    """문서 하나를 한 형식으로 파싱해 보는 시험 한 건."""

    doc_id: str
    format: str  # hwp | hwpx
    track: str  # structure | text
    truth: str  # hwpx | pdf
    path: Path
    tags: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.doc_id}.{self.format}"


def entries(manifest: Path = MANIFEST) -> list[dict]:
    return [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]


def file_path(entry: dict, fmt: str) -> Path:
    return ROOT / entry["files"][fmt]["path"]


def tests(manifest: Path = MANIFEST) -> list[Case]:
    out = []
    for e in entries(manifest):
        for t in e["tests"]:
            out.append(Case(e["id"], t["format"], t["track"], t["truth"], file_path(e, t["format"]), tuple(e.get("tags", []))))
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(manifest: Path = MANIFEST, log=print) -> int:
    """저장소에 넣지 않은 파일을 원 출처에서 받아 해시를 확인한다. 받은 개수를 돌려준다."""
    fetched = 0
    for e in entries(manifest):
        for fmt, f in e["files"].items():
            dest = ROOT / f["path"]
            if dest.exists() and _sha256(dest) == f["sha256"]:
                continue
            if not str(f.get("url", "")).startswith("https://"):
                raise RuntimeError(f"{e['id']} {fmt}: https 내려받기 주소가 없습니다")
            req = urllib.request.Request(f["url"], headers={"User-Agent": "hwp-parse-bench"})  # noqa: S310 - https만
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                data = resp.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD:
                raise RuntimeError(f"{e['id']} {fmt}: 파일이 너무 큽니다")
            if hashlib.sha256(data).hexdigest() != f["sha256"]:
                raise RuntimeError(f"{e['id']} {fmt}: 해시가 다릅니다. 출처 파일이 바뀌었을 수 있습니다")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            fetched += 1
            log(f"받음 {e['id']} {fmt}")
            # 공공 사이트에 부담을 주지 않도록 요청 사이를 띄운다
            time.sleep(REQUEST_INTERVAL)
    return fetched
