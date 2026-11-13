# /// script
# requires-python = "==3.11.*"
# dependencies = ["pyhwp==0.1b15", "six==1.17.0", "defusedxml==0.7.1"]
#
# [tool.uv]
# exclude-newer = "2026-11-06T00:00:00Z"
# ///
"""pyhwp 어댑터. 사용법: uv run --script adapters/pyhwp.py <입력> <출력>

- pyhwp는 AGPL-3.0이라 import하지 않고 같은 환경의 hwp5html 명령을 별도 프로세스로 실행한다.
- Python 3.11에 고정한다. setup.py가 distutils를 import하는데, distutils는 3.12에서 빠졌다.
- six는 pyhwp가 import하면서도 의존성으로 선언하지 않아 직접 넣는다.
- pyhwp에는 Markdown 출력이 없다. hwp5html이 만든 XHTML을 표준 라이브러리로 읽어, 문단은 한 줄씩,
  표는 rowspan·colspan만 남긴 HTML 표로 옮긴다(표 안 표는 칸 안에 그대로 둔다). 그림·서식은 버린다.
  이 변환은 우리 코드이므로 pyhwp 점수에는 어댑터의 몫이 조금 섞인다.
- HWP5만 읽는다. HWPX는 실패로 끝낸다.
"""

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET  # 형식 표기용. 파싱은 defusedxml로 한다
from html import escape
from pathlib import Path

# 스크립트 폴더를 import 경로에서 뺀다. 그대로 두면 adapters/unhwp.py 같은 파일이 같은 이름의 패키지를 가린다.
if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    del sys.path[0]

from defusedxml.ElementTree import parse as safe_parse  # noqa: E402

OLE_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
XHTML = "{http://www.w3.org/1999/xhtml}"


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean(text: str) -> str:
    return " ".join(text.replace("\r", " ").split())


def table_html(table: ET.Element) -> str:
    rows = []
    for tr in table.iter():
        # 표 안 표의 행은 바깥 표에서 건너뛴다. 그 표는 칸 안에서 따로 그린다.
        if local(tr.tag) != "tr" or owner_table(tr) is not table:
            continue
        cells = []
        for td in tr:
            if local(td.tag) not in ("td", "th"):
                continue
            attrs = "".join(f' {name}="{td.get(name)}"' for name in ("rowspan", "colspan") if td.get(name, "1") not in ("1", ""))
            cells.append(f"<td{attrs}>{cell_html(td)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


_parents: dict[ET.Element, ET.Element] = {}  # ElementTree에는 부모 링크가 없어 convert()가 채운다


def owner_table(element: ET.Element) -> ET.Element | None:
    """element를 감싼 가장 가까운 table."""
    node = _parents.get(element)
    while node is not None and local(node.tag) != "table":
        node = _parents.get(node)
    return node


def cell_html(td: ET.Element) -> str:
    parts: list[str] = []
    for kind, value in flow(td):
        parts.append(escape(value, quote=False) if kind == "text" else value)
    return "<br>".join(p for p in parts if p)


def flow(element: ET.Element):
    """element 아래를 문서 순서로 훑어 ("text", 문단 글) 또는 ("table", HTML) 을 낸다."""
    buffer: list[str] = []

    def walk(node: ET.Element):
        name = local(node.tag)
        if name == "table":
            yield from flush()
            yield ("table", table_html(node))
            if node.tail:
                buffer.append(node.tail)
            return
        if name == "p":
            yield from flush()
        if node.text and name not in ("style", "script"):
            buffer.append(node.text)
        for child in node:
            yield from walk(child)
        if name == "p":
            yield from flush()
        if node.tail:
            buffer.append(node.tail)

    def flush():
        text = clean("".join(buffer))
        buffer.clear()
        if text:
            yield ("text", text)

    for child in element:
        yield from walk(child)
    yield from flush()


def convert(src: str) -> str:
    with open(src, "rb") as f:
        if f.read(8) != OLE_MAGIC:
            raise ValueError("pyhwp는 HWP5(OLE)만 읽는다")
    hwp5html = Path(sys.executable).parent / "hwp5html"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "html"
        proc = subprocess.run([str(hwp5html), "--output", str(out), src], capture_output=True, text=True, check=False)
        index = out / "index.xhtml"
        if proc.returncode != 0 or not index.exists():
            last = (proc.stderr.strip().splitlines() or ["hwp5html 실패"])[-1]
            raise RuntimeError(f"hwp5html 종료 코드 {proc.returncode}: {last}")
        root = safe_parse(index).getroot()
    _parents.clear()
    _parents.update({child: parent for parent in root.iter() for child in parent})
    body = root.find(f"{XHTML}body")
    if body is None:
        body = root.find("body")
    if body is None:
        raise ValueError("hwp5html 출력에 body가 없다")
    blocks = [value for _, value in flow(body)]
    return "\n\n".join(blocks) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("사용법: uv run --script adapters/pyhwp.py <입력> <출력>")
    try:
        output = convert(sys.argv[1])
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 한 줄로 알린다
        sys.exit(f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"[:300])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        out.write(output)
