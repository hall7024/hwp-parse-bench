"""정답 만들기와 읽기.

- structure 트랙: HWPX 원본 → 참조 추출기 → truth/<id>.json
- text 트랙: 한컴이 만든 PDF → 텍스트 → truth/<id>.txt (순서와 무관한 글자 재현율에만 쓰는 약한 정답)
"""

from __future__ import annotations

import json
import re

from pypdf import PdfReader

from . import reference
from .corpus import ROOT, entries, file_path
from .model import Document, mask_contacts, normalize_text
from .render import to_markdown

TRUTH = ROOT / "truth"
EXTRACTOR_VERSION = "4"
_PAGE_NUMBER = re.compile(r"^\s*-\s*\d{1,4}\s*-\s*$")


def build(only: set[str] | None = None, log=print) -> int:
    """정답 파일을 만든다. 사람이 검수한(reviewed) 정답은 덮어쓰지 않는다."""
    TRUTH.mkdir(exist_ok=True)
    made = 0
    for e in entries():
        if only and e["id"] not in only:
            continue
        sources = {t["truth"] for t in e["tests"]}
        if "hwpx" in sources:
            path = TRUTH / f"{e['id']}.json"
            if path.exists() and json.loads(path.read_text(encoding="utf-8"))["status"] == "reviewed":
                log(f"건너뜀(검수됨) {e['id']}")
                continue
            doc = reference.extract(file_path(e, "hwpx"))
            data = {
                "id": e["id"],
                "source": e["files"]["hwpx"]["sha256"],
                "status": "auto",
                "extractor": EXTRACTOR_VERSION,
                "blocks": doc.to_json(),
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            (TRUTH / f"{e['id']}.md").write_text(to_markdown(doc), encoding="utf-8")
            made += 1
        if "pdf" in sources:
            reader = PdfReader(file_path(e, "pdf"))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            # 쪽 번호 줄("- 1 -")은 본문이 아니다. 숫자만 있는 줄은 표 칸일 수 있어 그대로 둔다
            text = "\n".join(line for line in text.splitlines() if not _PAGE_NUMBER.match(line))
            (TRUTH / f"{e['id']}.txt").write_text(mask_contacts(text), encoding="utf-8")
            made += 1
    return made


def load_document(doc_id: str) -> tuple[Document, str]:
    data = json.loads((TRUTH / f"{doc_id}.json").read_text(encoding="utf-8"))
    return Document.from_json(data["blocks"]), data["status"]


def load_text(doc_id: str) -> str:
    return normalize_text((TRUTH / f"{doc_id}.txt").read_text(encoding="utf-8"))
