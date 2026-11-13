import zipfile

import pytest

from hwpbench.model import Cell, Footnote, Heading, Paragraph, Table
from hwpbench.reference import HwpxError, extract

NS = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'

HEADER = f"""<?xml version="1.0" encoding="UTF-8"?>
<hh:head {NS}><hh:refList><hh:paraProperties>
  <hh:paraPr id="0"><hh:heading type="NONE" idRef="0" level="0"/></hh:paraPr>
  <hh:paraPr id="5"><hh:heading type="OUTLINE" idRef="0" level="0"/></hh:paraPr>
  <hh:paraPr id="6"><hh:heading type="OUTLINE" idRef="0" level="1"/></hh:paraPr>
</hh:paraProperties></hh:refList></hh:head>"""


def p(inner: str, pr: str = "0") -> str:
    return f'<hp:p paraPrIDRef="{pr}"><hp:run>{inner}</hp:run></hp:p>'


def tc(text: str, rs: int = 1, cs: int = 1) -> str:
    return f'<hp:tc><hp:subList>{p(f"<hp:t>{text}</hp:t>")}</hp:subList><hp:cellSpan colSpan="{cs}" rowSpan="{rs}"/></hp:tc>'


def hwpx(tmp_path, *paragraphs: str, name="doc.hwpx"):
    section = f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" {NS}>{"".join(paragraphs)}</hs:sec>'
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/header.xml", HEADER)
        zf.writestr("Contents/section0.xml", section)
    return path


def test_headings_paragraphs_and_spaces(tmp_path):
    doc = extract(
        hwpx(
            tmp_path,
            p("<hp:t>1. 개요</hp:t>", "5"),
            p("<hp:t>가. 세부</hp:t>", "6"),
            p("<hp:t>본문<hp:tab/>탭<hp:lineBreak/>줄</hp:t><hp:t>이어짐</hp:t>"),
            p("<hp:t> </hp:t>"),
        )
    )
    assert doc.blocks == [Heading(1, "1. 개요"), Heading(2, "가. 세부"), Paragraph("본문 탭 줄이어짐")]


def test_table_with_spans_nested_table_and_cell_footnote(tmp_path):
    nested = f"<hp:tbl><hp:tr>{tc('안쪽')}</hp:tr></hp:tbl>"
    cell_with_note = (
        f"<hp:tc><hp:subList>{p('<hp:t>값</hp:t><hp:ctrl><hp:footNote><hp:subList>' + p('<hp:t>칸 각주</hp:t>') + '</hp:subList></hp:footNote></hp:ctrl>')}"
        '</hp:subList><hp:cellSpan colSpan="1" rowSpan="1"/></hp:tc>'
    )
    table = (
        f"<hp:tbl><hp:tr>{tc('A', rs=2)}{tc('B', cs=2)}</hp:tr>"
        f'<hp:tr><hp:tc><hp:subList>{p(nested)}</hp:subList><hp:cellSpan colSpan="1" rowSpan="1"/></hp:tc>{cell_with_note}</hp:tr></hp:tbl>'
    )
    doc = extract(hwpx(tmp_path, p("<hp:t>표 앞</hp:t>" + table + "<hp:t>표 뒤</hp:t>")))
    assert doc.blocks == [
        Paragraph("표 앞"),
        Table(((Cell("A", 2, 1), Cell("B", 1, 2)), (Cell("안쪽"), Cell("값")))),
        Paragraph("표 뒤"),
        Footnote("칸 각주"),
    ]


def test_skips_header_footer_and_keeps_textbox(tmp_path):
    header = f"<hp:ctrl><hp:header><hp:subList>{p('<hp:t>머리말</hp:t>')}</hp:subList></hp:header></hp:ctrl>"
    textbox = f"<hp:rect><hp:drawText><hp:subList>{p('<hp:t>글상자</hp:t>')}</hp:subList></hp:drawText></hp:rect>"
    doc = extract(hwpx(tmp_path, p(header + "<hp:t>본문</hp:t>"), p(textbox)))
    assert doc.blocks == [Paragraph("본문"), Paragraph("글상자")]


def test_not_hwpx(tmp_path):
    path = tmp_path / "x.hwpx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "x")
    with pytest.raises(HwpxError):
        extract(path)


def test_rejects_entities(tmp_path):
    bomb = '<!DOCTYPE x [<!ENTITY a "AAAA">]>'
    path = tmp_path / "e.hwpx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "Contents/section0.xml",
            f'<?xml version="1.0"?>{bomb}<hs:sec xmlns:hs="s" {NS}>{p("<hp:t>&a;</hp:t>")}</hs:sec>',
        )
    doc = extract(path)
    assert "AAAA" not in doc.full_text()


def test_nested_table_paragraphs_are_separated(tmp_path):
    inner = f"<hp:tbl><hp:tr>{tc('윤건영')}{tc('▪ 가입 금지')}</hp:tr><hp:tr>{tc('김장겸')}{tc('▪ 정의 신설')}</hp:tr></hp:tbl>"
    outer = f'<hp:tbl><hp:tr><hp:tc><hp:subList>{p(inner)}</hp:subList><hp:cellSpan colSpan="1" rowSpan="1"/></hp:tc></hp:tr></hp:tbl>'
    [table] = extract(hwpx(tmp_path, p(outer))).blocks
    assert table.rows[0][0].text == "윤건영 ▪ 가입 금지 김장겸 ▪ 정의 신설"


def test_switch_hidden_comment_and_caption(tmp_path):
    switch = "<hp:switch><hp:case><hp:t>대안</hp:t></hp:case><hp:default><hp:t>기본</hp:t></hp:default></hp:switch>"
    hidden = f"<hp:ctrl><hp:hiddenComment><hp:subList>{p('<hp:t>숨은 설명</hp:t>')}</hp:subList></hp:hiddenComment></hp:ctrl>"
    table = f"<hp:tbl><hp:caption><hp:subList>{p('<hp:t>표 1. 현황</hp:t>')}</hp:subList></hp:caption><hp:tr>{tc('칸')}</hp:tr></hp:tbl>"
    doc = extract(hwpx(tmp_path, p(switch + hidden), p(table)))
    assert doc.blocks == [Paragraph("기본"), Table(((Cell("칸"),),)), Paragraph("표 1. 현황")]
