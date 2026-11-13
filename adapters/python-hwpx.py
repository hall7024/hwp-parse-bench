# /// script
# requires-python = "==3.12.*"
# dependencies = ["python-hwpx==6.11.0"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""python-hwpx 어댑터. 사용법: uv run --script adapters/python-hwpx.py <입력> <출력>

라이브러리의 Markdown 변환기(hwpx.ingest)가 쓰는 것과 같은 호출을 쓴다: markdown(rich=True, detect_headings=True).
rich=True라야 각주·미주가 나오고 병합 칸이 있는 표가 HTML(rowspan·colspan)로 나온다.
.hwp는 HwpxDocument.open이 HWPX로 바꿔 읽는다(옮기지 못한 내용은 라이브러리가 conversion_report에 남긴다).
"""

import os
import sys

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

from hwpx import HwpxDocument  # noqa: E402


def convert(src: str) -> str:
    doc = HwpxDocument.open(src)
    try:
        return doc.text.markdown(rich=True, detect_headings=True)
    finally:
        doc.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/python-hwpx.py <입력> <출력>")
    try:
        markdown = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(markdown)
