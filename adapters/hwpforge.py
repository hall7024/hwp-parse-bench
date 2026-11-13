# /// script
# requires-python = "==3.12.*"
# dependencies = ["hwpforge==0.19.1"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""hwpforge 어댑터. 사용법: uv run --script adapters/hwpforge.py <입력> <출력>

to_md(mode="lossy")를 쓴다. "styled"(기본)는 스타일 frontmatter를 앞에 붙이고, "lossless"는 라이브러리 설명대로
기계 점검용 보기라 본문 비교에 맞지 않는다. lossy는 Markdown으로 못 나타내는 것을 빼고 경고만 남긴다.
Markdown 표는 파이프 표뿐이라 병합 칸은 표현되지 않는다. Document.open이 HWPX와 HWP5를 모두 읽는다.
"""

import os
import sys

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

from hwpforge import Document  # noqa: E402


def convert(src: str) -> str:
    return Document.open(src).to_md(mode="lossy").text


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/hwpforge.py <입력> <출력>")
    try:
        output = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(output)
