"""정답과 파서 출력이 함께 쓰는 문서 모델."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Literal

_SPACES = re.compile("[\\s\\u00a0\\u3000]+")
_ZERO_WIDTH = re.compile("[\\u200b-\\u200d\\u2060\\ufeff]")
# 사용자 정의 영역(PUA). 한컴 고유 기호가 여기 들어 있고, 파서마다 그대로 두거나 다른 글자로 바꾼다
_PUA = re.compile("[\\ue000-\\uf8ff\\U000f0000-\\U000ffffd\\U00100000-\\U0010fffd]")
# 가운뎃점 변형: ‧ ∙ ・ ㆍ(호환 아래아) ᆞ(아래아) → ·. 법령 문서는 ㆍ를 가운뎃점으로 쓴다
_MIDDLE_DOTS = str.maketrans(dict.fromkeys("\u2027\u2219\u30fb\u318d\u119e", "\u00b7"))
# 보도자료 담당자 연락처는 공개 정답에 남기지 않는다. 정답과 파서 출력을 같은 규칙으로 가린다
_PHONE = re.compile(r"(?<!\d)0\d{1,2}[-.)\s]{1,2}\d{3,4}[-.\s]\d{4}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def mask_contacts(text: str) -> str:
    """전화번호는 000-0000-0000, 전자우편은 x@x로 바꾼다."""
    return _EMAIL.sub("x@x", _PHONE.sub("000-0000-0000", text))


def normalize_text(text: str) -> str:
    """NFC, 제로폭 문자·PUA 제거, 가운뎃점 통일, 공백류를 한 칸으로, 연락처 가림. 정답과 파서 출력에 똑같이 쓴다."""
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = _PUA.sub("", text).translate(_MIDDLE_DOTS)
    return mask_contacts(_SPACES.sub(" ", text).strip())


@dataclass(frozen=True)
class Cell:
    text: str
    rowspan: int = 1
    colspan: int = 1


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    kind: Literal["heading"] = "heading"


@dataclass(frozen=True)
class Paragraph:
    text: str
    kind: Literal["paragraph"] = "paragraph"


@dataclass(frozen=True)
class ListItem:
    level: int
    text: str
    kind: Literal["list_item"] = "list_item"


@dataclass(frozen=True)
class Footnote:
    text: str
    kind: Literal["footnote"] = "footnote"


@dataclass(frozen=True)
class Table:
    """병합 셀은 좌상단 칸에만 둔다 (HTML 표와 같은 표현)."""

    rows: tuple[tuple[Cell, ...], ...]
    kind: Literal["table"] = "table"

    def cells(self) -> list[Cell]:
        return [c for row in self.rows for c in row]

    @property
    def is_grid(self) -> bool:
        """2행 2열 이상인 표. 1행·1열짜리 꾸밈 틀(제목 상자 등)을 가려내는 데 쓴다."""
        return len(self.rows) >= 2 and max((sum(c.colspan for c in r) for r in self.rows), default=0) >= 2

    @property
    def has_merged(self) -> bool:
        return any(c.rowspan > 1 or c.colspan > 1 for c in self.cells())


Block = Heading | Paragraph | ListItem | Footnote | Table


@dataclass
class Document:
    blocks: list[Block] = field(default_factory=list)

    def tables(self) -> list[Table]:
        return [b for b in self.blocks if isinstance(b, Table)]

    def headings(self) -> list[Heading]:
        return [b for b in self.blocks if isinstance(b, Heading)]

    def full_text(self) -> str:
        """표를 포함한 본문 글을 순서대로 (표는 행 우선). 각주는 위치가 파서마다 달라 뺀다."""
        parts: list[str] = []
        for b in self.blocks:
            if isinstance(b, Table):
                parts.extend(c.text for c in b.cells())
            elif not isinstance(b, Footnote):
                parts.append(b.text)
        return normalize_text(" ".join(parts))

    def body_text(self) -> str:
        """표와 각주를 뺀 본문 텍스트."""
        return normalize_text(" ".join(b.text for b in self.blocks if not isinstance(b, Table | Footnote)))

    def to_json(self) -> list[dict]:
        out = []
        for b in self.blocks:
            d = asdict(b)
            if isinstance(b, Table):
                d["rows"] = [[asdict(c) for c in row] for row in b.rows]
            out.append(d)
        return out

    @classmethod
    def from_json(cls, data: list[dict]) -> Document:
        blocks: list[Block] = []
        for d in data:
            kind = d["kind"]
            if kind == "heading":
                blocks.append(Heading(d["level"], d["text"]))
            elif kind == "paragraph":
                blocks.append(Paragraph(d["text"]))
            elif kind == "list_item":
                blocks.append(ListItem(d["level"], d["text"]))
            elif kind == "footnote":
                blocks.append(Footnote(d["text"]))
            elif kind == "table":
                rows = tuple(tuple(Cell(c["text"], c.get("rowspan", 1), c.get("colspan", 1)) for c in r) for r in d["rows"])
                blocks.append(Table(rows))
            else:
                raise ValueError(f"알 수 없는 블록: {kind}")
        return cls(blocks)
