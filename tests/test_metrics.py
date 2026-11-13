import pytest

from hwpbench.metrics import heading_score, table_score, teds, text_nid
from hwpbench.model import Cell, Document, Heading, Paragraph, Table


def t(*rows):
    return Table(tuple(tuple(c if isinstance(c, Cell) else Cell(c) for c in r) for r in rows))


def test_text_nid():
    a = Document([Paragraph("가나다라"), t(["마", "바"])])
    assert text_nid(a, a) == 1.0
    assert text_nid(a, Document([Paragraph("가나다라 마 바")])) == 1.0  # 표 여부와 무관하게 텍스트만
    assert text_nid(a, Document([])) == 0.0


def test_teds_identical_and_one_cell():
    a = t(["a", "b"], ["c", "d"])
    assert teds(a, a) == 1.0
    # 노드 6개(tr 2, td 4. table 루트는 PubTabNet처럼 세지 않음) 중 칸 하나의 글이 완전히 다름 → 1 - 1/6
    assert teds(a, t(["a", "b"], ["c", "x"])) == pytest.approx(1 - 1 / 6)
    # 1×1 표의 글이 완전히 다르면 0.5 (PubTabNet과 같은 값)
    assert teds(t(["a"]), t(["b"])) == pytest.approx(0.5)
    assert teds(a, t(["a", "b"], ["c", "x"]), structure_only=True) == 1.0


def test_teds_span_mismatch_is_structural():
    a = t([Cell("a", colspan=2)], ["b", "c"])
    b = t(["a", ""], ["b", "c"])
    assert teds(a, b, structure_only=True) < 1.0


def test_table_score_matching_and_penalties():
    x, y = t(["1"]), t(["2", "3"])
    truth = Document([x, y])
    assert table_score(truth, Document([y, x])).teds == 1.0  # 순서가 달라도 짝을 찾는다
    missed = table_score(truth, Document([y]))
    assert missed.teds == pytest.approx(2 * 1.0 / 3)
    assert table_score(truth, Document([])).teds == 0.0
    assert table_score(Document([Paragraph("p")]), Document([x])).teds is None


def test_heading_score():
    truth = Document([Heading(1, "가"), Heading(2, "나")])
    assert heading_score(truth, Document([Heading(2, "가"), Heading(3, "나")])).f1_level == 1.0  # 상대 레벨
    s = heading_score(truth, Document([Heading(1, "가"), Heading(1, "나")]))
    assert (s.f1, s.f1_level) == (1.0, 0.5)
    assert heading_score(truth, Document([])).f1 == 0.0
    assert heading_score(Document([]), Document([Heading(1, "x")])).f1 is None


def test_nid_is_indel_based():
    from hwpbench.metrics import text_nid_s

    a = Document([Paragraph("abcd")])
    # indel 거리 2 (하나 빼고 하나 넣기) / 길이 합 8
    assert text_nid(a, Document([Paragraph("abce")])) == pytest.approx(1 - 2 / 8)
    assert text_nid_s(Document([t(["x"])]), a) is None


def test_char_f1_ignores_order_and_spaces():
    from hwpbench.metrics import char_f1

    assert char_f1("가 나 다", "다나가") == (1.0, 1.0, 1.0)
    r, p, _ = char_f1("가나", "가")
    assert (r, p) == (0.5, 1.0)


def test_table_subsets():
    frame = t(["제목 상자"])
    grid = t(["a", "b"], ["c", "d"])
    merged = t([Cell("a", colspan=2)], ["c", "d"])
    truth = Document([frame, grid, merged])
    pred = Document([grid, t(["a", ""], ["c", "d"])])  # 꾸밈 틀 누락, 병합을 표현 못 함
    assert table_score(truth, pred, "grid").teds < 1.0
    nomerge = table_score(truth, pred, "nomerge")
    # 병합 없는 격자 정답 표는 grid 하나. 꾸밈 틀과 병합 표는 빠지고, grid는 출력에서 그대로 찾는다
    assert (nomerge.truth_count, nomerge.teds) == (1, 1.0)
