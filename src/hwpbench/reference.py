"""독립 참조 추출기: HWPX(OWPML) XML → 문서 모델.

비교 대상 파서의 코드는 쓰지 않는다. lxml과 표준 라이브러리만 쓴다.
머리말·꼬리말·쪽 번호·수식은 넣지 않는다(RAG 본문이 아님). 각주·미주는 Footnote 블록으로 둔다.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from .model import Block, Cell, Document, Footnote, Heading, Paragraph, Table, normalize_text

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"

MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024

_parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_comments=True)
_SECTION = re.compile(r"^Contents/section(\d+)\.xml$")

# 본문 텍스트로 치지 않는 컨트롤
_SKIP = {
    f"{{{HP}}}{n}"
    # 머리말·꼬리말·쪽 번호·수식·숨은 설명, 그리고 hp:switch의 대안(case)은 본문이 아니다
    for n in ("header", "footer", "pageNum", "pageHiding", "equation", "fieldEnd", "secPr", "colPr", "hiddenComment", "case")
}
_NOTES = {f"{{{HP}}}footNote", f"{{{HP}}}endNote"}
_BOUNDARIES = {f"{{{HP}}}{n}" for n in ("tbl", "tr", "tc", "subList")}
_SPACE_TAGS = {f"{{{HP}}}{n}" for n in ("tab", "lineBreak", "nbSpace", "fwSpace")}


class HwpxError(Exception):
    pass


def _read(zf: zipfile.ZipFile, name: str) -> etree._Element:
    info = zf.getinfo(name)
    if info.file_size > MAX_ENTRY_BYTES:
        raise HwpxError(f"{name}이 너무 큽니다 ({info.file_size} bytes)")
    with zf.open(info) as f:
        data = f.read(MAX_ENTRY_BYTES + 1)
    if len(data) > MAX_ENTRY_BYTES:
        raise HwpxError(f"{name}이 너무 큽니다")
    return etree.fromstring(data, _parser)


def _outline_levels(header: etree._Element | None) -> dict[str, int]:
    """paraPr id → 개요 수준(1부터). hh:heading type="OUTLINE"인 문단 모양만."""
    levels: dict[str, int] = {}
    if header is None:
        return levels
    for pp in header.iter(f"{{{HH}}}paraPr"):
        h = pp.find(f"{{{HH}}}heading")
        if h is not None and h.get("type") == "OUTLINE":
            levels[pp.get("id", "")] = int(h.get("level", "0")) + 1
    return levels


class _Extractor:
    def __init__(self, outline: dict[str, int]):
        self.outline = outline
        self.notes: list[Footnote] = []

    def text_of(self, el: etree._Element) -> str:
        """el 아래 모든 텍스트(표·글상자 포함). 칸 텍스트, 중첩 표에 쓴다."""
        parts: list[str] = []
        self._collect(el, parts)
        return normalize_text(" ".join(parts))

    def _collect(self, el: etree._Element, parts: list[str]) -> None:
        for child in el:
            tag = child.tag
            if tag in _SKIP:
                continue
            if tag in _NOTES:
                # 표 칸 안의 각주도 각주 블록으로 (칸 텍스트에는 넣지 않음)
                self.notes.append(Footnote(self.text_of(child)))
                continue
            if tag == f"{{{HP}}}t":
                parts.append(self._t_text(child))
            elif tag == f"{{{HP}}}p":
                sub: list[str] = []
                self._collect(child, sub)
                parts.append("".join(sub))
            elif tag in _BOUNDARIES:
                # 문단 안에 든 표·칸·글상자는 앞뒤 글과 붙지 않게 띄운다 (같은 문단의 run은 공백 없이 붙이므로)
                parts.append(" ")
                self._collect(child, parts)
                parts.append(" ")
            else:
                self._collect(child, parts)

    @staticmethod
    def _t_text(t: etree._Element) -> str:
        parts = [t.text or ""]
        for child in t:
            parts.append(" " if child.tag in _SPACE_TAGS else "")
            parts.append(child.tail or "")
        return "".join(parts)

    def table(self, tbl: etree._Element) -> Table:
        rows = []
        for tr in tbl.findall(f"{{{HP}}}tr"):
            cells = []
            for tc in tr.findall(f"{{{HP}}}tc"):
                span = tc.find(f"{{{HP}}}cellSpan")
                rowspan = int(span.get("rowSpan", "1")) if span is not None else 1
                colspan = int(span.get("colSpan", "1")) if span is not None else 1
                body = tc.find(f"{{{HP}}}subList")
                cells.append(Cell(self.text_of(body) if body is not None else "", rowspan, colspan))
            rows.append(tuple(cells))
        return Table(tuple(rows))

    def paragraph(self, p: etree._Element, out: list[Block]) -> None:
        """문단 하나. 문단 안의 표·글상자는 만난 순서대로 별도 블록이 된다."""
        parts: list[str] = []

        def flush() -> None:
            # 같은 문단의 run은 글자 모양만 다를 뿐 이어진 글이라 공백 없이 붙인다
            text = normalize_text("".join(parts))
            parts.clear()
            if not text:
                return
            level = self.outline.get(p.get("paraPrIDRef", ""))
            out.append(Heading(level, text) if level else Paragraph(text))

        def walk(el: etree._Element) -> None:
            for child in el:
                tag = child.tag
                if tag in _SKIP:
                    continue
                if tag in _NOTES:
                    self.notes.append(Footnote(self.text_of(child)))
                elif tag == f"{{{HP}}}t":
                    parts.append(self._t_text(child))
                elif tag == f"{{{HP}}}tbl":
                    flush()
                    out.append(self.table(child))
                    caption = child.find(f"{{{HP}}}caption")
                    if caption is not None and (text := self.text_of(caption)):
                        out.append(Paragraph(text))
                elif tag == f"{{{HP}}}subList":
                    # 글상자 등 표 밖의 하위 문단 목록
                    flush()
                    for sp in child.findall(f"{{{HP}}}p"):
                        self.paragraph(sp, out)
                else:
                    walk(child)

        walk(p)
        flush()


def extract(path: str | Path) -> Document:
    with zipfile.ZipFile(path) as zf:
        if sum(i.file_size for i in zf.infolist()) > MAX_TOTAL_BYTES:
            raise HwpxError("압축 해제 크기가 너무 큽니다")
        names = zf.namelist()
        header = _read(zf, "Contents/header.xml") if "Contents/header.xml" in names else None
        sections = sorted((int(m.group(1)), n) for n in names if (m := _SECTION.match(n)))
        if not sections:
            raise HwpxError("본문 section이 없습니다 (HWPX가 아니거나 배포용 문서)")
        ex = _Extractor(_outline_levels(header))
        blocks: list[Block] = []
        for _, name in sections:
            root = _read(zf, name)
            for p in root.findall(f"{{{HP}}}p"):
                ex.paragraph(p, blocks)
        blocks.extend(ex.notes)
        return Document(blocks)
