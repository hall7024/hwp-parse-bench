"""문서 모델 → Markdown. 표는 병합 칸을 잃지 않게 HTML로 쓴다."""

from __future__ import annotations

from html import escape

from .model import Document, Footnote, Heading, ListItem, Paragraph, Table


def table_html(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = []
        for c in row:
            attrs = (f' rowspan="{c.rowspan}"' if c.rowspan > 1 else "") + (f' colspan="{c.colspan}"' if c.colspan > 1 else "")
            cells.append(f"<td{attrs}>{escape(c.text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def to_markdown(doc: Document) -> str:
    out: list[str] = []
    notes = 0
    for b in doc.blocks:
        if isinstance(b, Heading):
            out.append("#" * min(b.level, 6) + " " + b.text)
        elif isinstance(b, Paragraph):
            out.append(b.text)
        elif isinstance(b, ListItem):
            out.append("  " * (b.level - 1) + "- " + b.text)
        elif isinstance(b, Footnote):
            notes += 1
            out.append(f"[^{notes}]: {b.text}")
        elif isinstance(b, Table):
            out.append(table_html(b))
    return "\n\n".join(out) + "\n"
