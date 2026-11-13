# /// script
# requires-python = "==3.12.*"
# dependencies = ["llama-index-readers-hwp==0.6.0"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""LlamaIndex HWPReader 어댑터. 사용법: uv run --script adapters/llama-index-readers-hwp.py <입력> <출력>

HWP5(OLE)만 읽고 본문 텍스트만 낸다(표 구조 없음). HWPX는 지원하지 않아 실패로 끝낸다.
문서 여러 개가 나오면 빈 줄로 잇는다.
"""

import os
import sys

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

from pathlib import Path  # noqa: E402

from llama_index.readers.hwp import HWPReader  # noqa: E402

OLE_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")


def convert(src: str) -> str:
    with open(src, "rb") as f:
        if f.read(8) != OLE_MAGIC:
            raise ValueError("HWPReader는 HWP5(OLE)만 읽는다")
    documents = HWPReader().load_data(file=Path(src))
    return "\n\n".join(document.text for document in documents)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/llama-index-readers-hwp.py <입력> <출력>")
    try:
        output = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(output)
