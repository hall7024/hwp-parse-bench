# /// script
# requires-python = "==3.12.*"
# dependencies = ["rhwp-python==0.8.1"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""rhwp-python 어댑터. 사용법: uv run --script adapters/rhwp-python.py <입력> <출력>

라이브러리의 IR Markdown 렌더러(Document.to_ir().to_markdown())를 쓴다. 병합 칸이 없는 표는 GFM 표, 병합 칸이
있으면 HTML(rowspan·colspan)로 낸다. 각주·미주는 끝에 [^N] 정의로 붙고, 머리말·꼬리말은 넣지 않는다.
Document.extract_text()는 표 안 글을 내지 않아(샘플 보도자료에서 확인) 쓰지 않는다.
"""

import os
import sys

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

import rhwp  # noqa: E402


def convert(src: str) -> str:
    return rhwp.parse(src).to_ir().to_markdown()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/rhwp-python.py <입력> <출력>")
    try:
        output = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(output)
