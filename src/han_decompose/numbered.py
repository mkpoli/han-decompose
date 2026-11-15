"""The numbered components of BabelStone IDS and the glyphs BabelStone Han PUA draws for them.

Note 6 of IDS.TXT lists each unencoded component with the code point it has in the private use
area of BabelStone Han PUA. That glyph is the component's reference shape: a cut of the component
is held against it, and it is the form the component takes where no font of a chain yields one.
The code points belong to one version of the font and move between versions.
"""

from pathlib import Path

from . import descriptions, pins
from . import identifiers as I
from .outline import Face
from .pieces import Drawing, Glyph
from .schema import Json

FONT = "babelstone-han-pua@1.472"


def rows(table: descriptions.Table) -> list[Json]:
    """A row of the component tables per numbered component: the component is the character at
    its code point in BabelStone Han PUA, by note 6. A component note 6 gives no code point has a
    row that only names it."""
    version = pins.font(FONT)["version"]
    out: list[Json] = []
    for name in sorted(table.numbered, key=lambda name: int(name[1:-1])):
        row = table.numbered[name]
        base: Json = {"component": I.component_of(name), "kind": "babelstone", "text": name}
        if row.pua:
            target = I.component("u", f"{ord(row.pua):04X}")
            basis = f"IDS.TXT note 6: its code point in BabelStone Han PUA {version} ({row.where})"
            out.append({**base, "relation": "same", "target": target, "basis": basis, "tier": "source"})
        else:
            out.append({**base, "relation": "", "target": "", "basis": "", "tier": ""})
        out[-1]["source"] = "babelstone"
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
