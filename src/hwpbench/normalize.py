"""파서 출력(Markdown, GFM 표, HTML 표, 일반 텍스트)을 문서 모델로."""

from __future__ import annotations

import re

import lxml.html
from markdown_it import MarkdownIt
from markdown_it.token import Token

from .model import Block, Cell, Document, Footnote, Heading, ListItem, Paragraph, Table, normalize_text

_md = MarkdownIt("commonmark").enable("table")


_FOOTREF = re.compile(r"\[\^[^\]\s]+\]")
_FOOTDEF = re.compile(r"^\[\^[^\]\s]+\]:\s*(.*)$", re.S)


def _inline_text(token: Token) -> str:
    parts: list[str] = []
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif child.type == "html_inline":
            if child.content.lower().startswith("<br"):
                parts.append(" ")
        elif child.type == "image":
            continue
    # 각주 참조 표시([^1])는 글이 아니다
    return normalize_text(_FOOTREF.sub("", "".join(parts)))


def _md_inline(text: str) -> str:
    """HTML 안에 섞여 나온 Markdown 강조(**굵게** 등)를 글만 남긴다."""
    tokens = _md.parseInline(text)
    return _inline_text(tokens[0]) if tokens else ""


# 이 요소 앞뒤는 글이 붙지 않게 띄운다
_BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "tr", "td", "th", "table", "br", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}


def _raw_text(el) -> str:
    parts = [el.text or ""]
    for child in el:
        if isinstance(child.tag, str):
            gap = " " if child.tag in _BLOCK_TAGS else ""
            parts += [gap, _raw_text(child), gap]
        parts.append(child.tail or "")
    return "".join(parts)


def _span(el, name: str) -> int:
    try:
        return max(1, int(el.get(name, "1")))
    except ValueError:
        return 1


def _html_table(tbl) -> Table:
    """표 안의 표는 그 칸의 글로 들어간다."""
    rows = []
    for tr in tbl.iter("tr"):
        if next((a for a in tr.iterancestors() if a.tag == "table"), None) is not tbl:
            continue
        cells = tuple(Cell(_md_inline(_raw_text(td)), _span(td, "rowspan"), _span(td, "colspan")) for td in tr if td.tag in ("td", "th"))
        if cells:
            rows.append(cells)
    return Table(tuple(rows))


def html_blocks(html: str) -> list[Block]:
    """HTML 조각을 문서 순서대로 블록으로. 최상위 표는 Table, 표 사이·앞뒤 글은 Paragraph."""
    root = lxml.html.fragment_fromstring(html, create_parent="div")
    blocks: list[Block] = []
    buf: list[str] = []

    def flush() -> None:
        text = _md_inline(" ".join(buf))
        buf.clear()
        if text:
            blocks.append(Paragraph(text))

    def walk(el) -> None:
        buf.append(el.text or "")
        for child in el:
            if not isinstance(child.tag, str):
                pass
            elif child.tag == "table":
                flush()
                blocks.append(_html_table(child))
            elif child.find(".//table") is not None:
                walk(child)
            else:
                gap = " " if child.tag in _BLOCK_TAGS else ""
                buf.extend([gap, _raw_text(child), gap])
            buf.append(child.tail or "")

    walk(root)
    flush()
    return blocks


def html_tables(html: str) -> list[Table]:
    return [b for b in html_blocks(html) if isinstance(b, Table)]


def from_markdown(text: str) -> Document:
    tokens = _md.parse(text)
    lines = text.splitlines()
    blocks: list[Block] = []
    list_depth = 0
    in_item = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
        elif t.type in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
        elif t.type == "list_item_open":
            in_item = True
        elif t.type == "list_item_close":
            in_item = False
        elif t.type == "heading_open":
            blocks.append(Heading(int(t.tag[1:]), _inline_text(tokens[i + 1])))
            i += 2
        elif t.type == "paragraph_open":
            footnote = _FOOTDEF.match(tokens[i + 1].content)
            if footnote:
                blocks.append(Footnote(_md_inline(footnote.group(1))))
            else:
                content = _inline_text(tokens[i + 1])
                if content:
                    blocks.append(ListItem(list_depth, content) if in_item and list_depth else Paragraph(content))
            i += 2
        elif t.type == "table_open":
            blocks.append(_pipe_table(lines[t.map[0] : t.map[1]]) if t.map else Table(()))
            while tokens[i].type != "table_close":
                i += 1
        elif t.type == "html_block":
            # html_block은 빈 줄까지 이어지므로 표 뒤에 붙은 글도 같은 블록에 들어온다. 순서대로 나눠 담는다
            blocks.extend(html_blocks(t.content))
        elif t.type in ("fence", "code_block"):
            content = normalize_text(t.content)
            if content:
                blocks.append(Paragraph(content))
        i += 1
    return Document(blocks)


_PIPE = re.compile(r"(?<!\\)\|")
_DELIMITER = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _pipe_table(lines: list[str]) -> Table:
    """GFM 파이프 표를 줄 단위로 직접 나눈다.

    markdown-it은 머리 행보다 칸이 많은 행의 남는 칸을 버린다. 실제 파서 출력에는 머리 행이 1칸이고
    본문이 3칸인 표가 있어, 그대로 쓰면 글이 사라진 것으로 채점된다. 여기서는 모든 칸을 살린다.
    """
    rows = []
    for line in lines:
        if _DELIMITER.match(line):
            continue
        body = line.strip()
        body = body[1:] if body.startswith("|") else body
        body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
        cells = tuple(Cell(_inline_text(_md.parseInline(c.replace("\\|", "|"))[0])) for c in _PIPE.split(body))
        rows.append(cells)
    return Table(tuple(rows))


def from_plain_text(text: str) -> Document:
    """표·제목을 내지 않는 파서용. 빈 줄로 나뉜 덩어리를 문단으로 본다."""
    blocks: list[Block] = []
    for chunk in text.replace("\r\n", "\n").split("\n\n"):
        content = normalize_text(chunk)
        if content:
            blocks.append(Paragraph(content))
    return Document(blocks)
