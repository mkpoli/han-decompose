"""The Adobe-Japan1 glyphs that descriptions name, as rows of the component tables.

Descriptions write a glyph of the Adobe-Japan1 collection that has no code point of its own as an
entity, `&AJ1-01815;`: CID 1815. Adobe's kanji table says which character each CID is a glyph of:
the kanji of JIS X 0208 it is the base glyph of, the code point the UniJIS CMap reaches it
from, or the variation sequence registered for it. Each CID gives a row: it is a glyph of a character.
"""

import re
from collections.abc import Iterable
from pathlib import Path

from . import identifiers as I
from . import pins
from .schema import Json

#: The CIDs of Adobe-Japan1 that descriptions write as an entity `&AJ1-NNNNN;`: the 164 of the
#: component registry of ids-input at commit be70733a179085a16e48f7049b6cfec5e07f4496.
# fmt: off
CIDS = (
    1148, 1189, 1227, 1245, 1276, 1341, 1384, 1394, 1405, 1445, 1455, 1480,
    1562, 1586, 1614, 1620, 1679, 1706, 1731, 1755, 1771, 1792, 1815, 1829,
    1866, 1885, 1925, 1939, 2014, 2062, 2067, 2089, 2109, 2115, 2116, 2164,
    2174, 2180, 2215, 2267, 2349, 2356, 2362, 2399, 2413, 2423, 2541, 2585,
    2653, 2665, 2686, 2708, 2755, 2761, 2873, 3011, 3071, 3080, 3126, 3180,
    3231, 3246, 3273, 3314, 3446, 3523, 3652, 3690, 3724, 3729, 3790, 3831,
    3910, 4017, 4110, 4209, 4215, 4216, 4270, 4307, 4312, 4319, 4352, 4376,
    4449, 4551, 4632, 4636, 4721, 4830, 4956, 5344, 5455, 5511, 5564, 5603,
    5786, 5807, 5916, 5917, 6205, 6233, 6323, 6479, 6608, 6773, 6885, 7006,
    7042, 7070, 7078, 7146, 7208, 7300, 7417, 7430, 7443, 7449, 7672, 7826,
    8403, 8425, 8598, 8627, 13342, 13365, 13698, 13701, 13763, 14417, 14521, 14542,
    15044, 15391, 16955, 17085, 17236, 17246, 17466, 17535, 17537, 17560, 17590, 17632,
    17729, 17810, 17839, 18030, 18056, 18113, 18194, 18400, 18448, 18690, 19346, 19486,
    21076, 21105, 21253, 21281, 21323, 21334, 21605, 21607,
)
# fmt: on
_SEQUENCE = re.compile(r"<U\+([0-9A-F]+),U\+([0-9A-F]+)>")
_POINT = re.compile(r"U\+([0-9A-F]+)")


def table(path: Path) -> dict[int, list[str]]:
    """Adobe's `aj17-kanji.txt` by CID: the 21 fields of each line."""
    out = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 21:
            raise ValueError(f"aj17-kanji.txt: {len(fields)} fields in the line of CID {fields[0]}.")
        out[int(fields[0])] = fields
    return out


def glyph_of(fields: list[str]) -> tuple[str, str, str]:
    """The character a CID is a glyph of, as a component reference, with what the relation rests
    on and its kind: `jis` (the base glyph of a JIS X 0208 kanji), `code-point` (a later addition
    that the UniJIS CMap reaches from a code point) or `sequence` (reached only by a variation
    sequence).

    The character is the base of the CID's variation sequence. That settles the CIDs the CMap
    reaches from a Kangxi radical as well as from its ideograph, and CID 15391, which it reaches
    from the radical U+2E95 alone: each is a glyph of the ideograph."""
    cid, jis, cmap, sequences = fields[0], fields[1], fields[17], fields[19]
    sequence = _SEQUENCE.search(sequences)
    points = _POINT.findall(cmap) if cmap != "*" else []
    if sequence is None and not points:
        raise ValueError(f"aj17-kanji.txt: CID {cid} has neither a code point nor a variation sequence.")
    target = I.component("u", sequence[1] if sequence is not None else points[0])
    basis = []
    if jis != "*":
        basis.append(f"field 2: the base glyph of JIS X 0208 {jis}")
    if points:
        basis.append("field 18: UniJIS-UTF32-H maps " + " and ".join(f"U+{point}" for point in points) + " to the CID")
    if sequence is not None:
        basis.append(f"field 20: the variation sequence <U+{sequence[1]},U+{sequence[2]}>")
    kind = "jis" if jis != "*" else "code-point" if points else "sequence"
    return target, "aj17-kanji.txt " + "; ".join(basis), kind


def rows(cids: Iterable[int], kanji: dict[int, list[str]]) -> list[Json]:
    """A row of the component tables per CID: the CID is a glyph of a character (Adobe's table)."""
    out: list[Json] = []
    for cid in sorted(cids):
        if cid not in kanji:
            raise ValueError(f"aj17-kanji.txt has no CID {cid}.")
        target, basis, _ = glyph_of(kanji[cid])
        out.append(
            {
                "component": I.component("aj1", str(cid)),
                "kind": "adobe-japan1",
                "text": "",
                "relation": "glyph-of",
                "target": target,
                "basis": basis,
                "tier": "source",
            }
        )
    return out


def pinned(cache: Path | None = None) -> list[Json]:
    """The rows for every CID of `CIDS`, from the pinned table."""
    paths = pins.source_paths(pins.source("adobe-japan1"), cache, fetch=False)
    return rows(CIDS, table(paths["aj17-kanji.txt"]))
