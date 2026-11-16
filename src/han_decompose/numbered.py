"""The numbered components of BabelStone IDS and the glyphs BabelStone Han PUA draws for them.

Note 6 of IDS.TXT lists each unencoded component with the code point it has in the private use
area of BabelStone Han PUA. That glyph is the component's reference shape: a cut of the component
is held against it, and it is the form the component takes where no font of a chain yields one.
The code points belong to one version of the font and move between versions.
"""

from pathlib import Path

from . import descriptions, pins
from . import identifiers as I
from .cutters.lift import PUA
from .outline import Face
from .pieces import Drawing, Glyph
from .schema import Json

#: The font whose private use area draws the numbered components.
FONT = PUA


def rows(table: descriptions.Table) -> list[Json]:
    """A row of the component table per numbered component: the component is the character at its
    code point in BabelStone Han PUA, by note 6. The code point holds for the pinned version of the
    font, which the row's basis names. A component note 6 gives no code point has a row that only
    names it."""
    version = pins.font(FONT)["version"]
    out: list[Json] = []
    for name in sorted(table.numbered, key=lambda name: int(name[5:-1])):
        row = table.numbered[name]
        base: Json = {"component": I.component_of(name), "kind": "numbered", "text": name}
        if row.pua:
            target = I.component("u", f"{ord(row.pua):04X}")
            basis = (
                f"IDS.TXT note 6 gives the component ({row.where}) this code point in the BabelStone Han PUA font; "
                f"version {version} of the font draws it there"
            )
            out.append({**base, "relation": "equivalent", "target": target, "basis": basis, "tier": "source"})
        else:
            out.append({**base, "relation": "", "target": "", "basis": "", "tier": ""})
    return out


def glyphs(table: descriptions.Table, cache: Path | None = None) -> dict[str, Glyph]:
    """The glyph of each numbered component in BabelStone Han PUA, by the component's text."""
    drawing = Drawing(Face.pinned(FONT, cache))
    out = {}
    for name, row in table.numbered.items():
        glyph = drawing.glyph(f"U+{ord(row.pua):04X}") if row.pua else None
        if glyph is not None and glyph.contours:
            out[name] = glyph
    return out
