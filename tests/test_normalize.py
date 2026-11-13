from hwpbench.model import Cell, Document, Heading, ListItem, Paragraph, Table, normalize_text
from hwpbench.normalize import from_markdown, from_plain_text


def test_normalize_text():
    assert normalize_text(" 가\u3000나\u200b다\n\n라 ") == "가 나다 라"
    # NFD 한글을 NFC로
    assert normalize_text("가") == "가"


def test_headings_paragraphs_lists():
    doc = from_markdown("# 제목\n\n본문 **강조** 문장\n\n- 하나\n  - 둘\n")
    assert doc.blocks == [Heading(1, "제목"), Paragraph("본문 강조 문장"), ListItem(1, "하나"), ListItem(2, "둘")]


def test_gfm_table_with_escaped_pipe_and_br():
    doc = from_markdown("| 가 | 나 |\n|---|---|\n| a\\|b | 줄1<br>줄2 |\n")
    assert doc.blocks == [Table(((Cell("가"), Cell("나")), (Cell("a|b"), Cell("줄1 줄2"))))]


def test_html_table_spans_and_nested():
    html = (
        '<table><tr><td rowspan="2">A</td><td colspan="2">B</td></tr>'
        "<tr><td>C</td><td><table><tr><td>안</td></tr></table></td></tr></table>\n"
    )
    [table] = from_markdown(html).blocks
    assert table.rows == ((Cell("A", 2, 1), Cell("B", 1, 2)), (Cell("C"), Cell("안")))


def test_html_table_between_paragraphs():
    doc = from_markdown("앞\n\n<table><tr><th>머리</th></tr></table>\n\n뒤\n")
    assert [b.kind for b in doc.blocks] == ["paragraph", "table", "paragraph"]


def test_plain_text():
    assert from_plain_text("첫 문단\n이어짐\n\n둘째").blocks == [Paragraph("첫 문단 이어짐"), Paragraph("둘째")]


def test_json_roundtrip():
    doc = Document([Heading(2, "h"), Table(((Cell("x", 2, 1),),)), ListItem(1, "l")])
    assert Document.from_json(doc.to_json()) == doc


def test_pipe_table_keeps_extra_cells_beyond_header():
    md = "| 분류표 |\n| --- |\n| 구분 | 번호 | 품명 |\n| 1. 곡류 | 1001 | 밀 |\n"
    [table] = from_markdown(md).blocks
    assert table.rows == ((Cell("분류표"),), (Cell("구분"), Cell("번호"), Cell("품명")), (Cell("1. 곡류"), Cell("1001"), Cell("밀")))


def test_html_block_keeps_text_around_table():
    doc = from_markdown("<table><tr><td>칸</td></tr></table>\n표 바로 뒤 문단\n\n다음 문단\n")
    assert doc.blocks == [Table(((Cell("칸"),),)), Paragraph("표 바로 뒤 문단"), Paragraph("다음 문단")]


def test_html_cell_separates_blocks_and_strips_markdown():
    html = "<table><tr><td><p>문단1</p><p>**문단2**</p></td><td>바깥<table><tr><td>가</td><td>나</td></tr></table></td></tr></table>\n"
    [table] = from_markdown(html).blocks
    assert [c.text for c in table.rows[0]] == ["문단1 문단2", "바깥 가 나"]


def test_footnotes():
    from hwpbench.model import Footnote

    doc = from_markdown("본문[^1] 이어짐\n\n[^1]: 각주 글\n")
    assert doc.blocks == [Paragraph("본문 이어짐"), Footnote("각주 글")]
    assert doc.full_text() == "본문 이어짐"


def test_contacts_masked_both_sides():
    assert normalize_text("담당 (044-123-4567) hong@example.com") == "담당 (000-0000-0000) x@x"
    assert normalize_text("02)1234-5678, 010 1234 5678") == "000-0000-0000, 000-0000-0000"
    # 날짜·금액 같은 다른 숫자는 그대로
    assert normalize_text("2026-11-13, 1,234-5678원") == "2026-11-13, 1,234-5678원"
