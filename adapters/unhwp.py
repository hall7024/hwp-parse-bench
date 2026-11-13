# /// script
# requires-python = "==3.12.*"
# dependencies = ["unhwp==0.23.1"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""unhwp 어댑터. 사용법: uv run --script adapters/unhwp.py <입력> <출력>

병합 칸이 있는 표는 HTML(rowspan·colspan)로 내게 한다(table_fallback="html"). 기본값 "markdown"은
병합 칸의 글을 첫 칸에만 넣어 표 모양이 무너진다. 글을 바꾸는 cleanup은 켜지 않는다.
"""

import os
import sys

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

import unhwp  # noqa: E402
from unhwp import RenderOptions  # noqa: E402


def convert(src: str) -> str:
    result = unhwp.parse(src, render_options=RenderOptions(table_fallback="html"))
    try:
        return result.markdown
    finally:
        result.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/unhwp.py <입력> <출력>")
    try:
        markdown = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(markdown)
