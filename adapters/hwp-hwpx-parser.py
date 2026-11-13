# /// script
# requires-python = "==3.12.*"
# dependencies = ["hwp-hwpx-parser==1.0.0"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""hwp-hwpx-parser 어댑터. 사용법: uv run --script adapters/hwp-hwpx-parser.py <입력> <출력>

표를 Markdown 표로 내는 옵션(TableStyle.MARKDOWN)을 쓴다. 이 라이브러리에는 HTML 표 출력이 없어 병합 칸은 표현되지 않는다.
그림 자리 표시는 끈다(ImageMarkerStyle.NONE). 각주·미주는 extract_text_with_notes로 받아 끝에 Markdown 각주([^n]: …)로 붙인다.
"""

import os
import sys

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

from hwp_hwpx_parser import ExtractOptions, ImageMarkerStyle, TableStyle, read  # noqa: E402


def convert(src: str) -> str:
    reader = read(src)
    try:
        options = ExtractOptions(table_style=TableStyle.MARKDOWN, image_marker=ImageMarkerStyle.NONE)
        result = reader.extract_text_with_notes(options)
    finally:
        reader.close()
    notes = [f"[^{note.number}]: {note.text}" for note in [*result.footnotes, *result.endnotes]]
    return result.text + ("\n\n" + "\n".join(notes) if notes else "")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/hwp-hwpx-parser.py <입력> <출력>")
    try:
        output = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(output)
