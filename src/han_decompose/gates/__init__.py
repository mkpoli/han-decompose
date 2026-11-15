"""Checks a cut has to pass: is the ink handed to a component shaped like the component?

Both checks compare the cut with the component as a font draws it alone, each stretched on its own
to fill a square, so size and proportion are set aside and the figure is what is compared. A cut
is measured against every font of the chain that draws the component and keeps its best reading.

The limits were set on 山: 208 cuts judged by eye (44 wrong, 164 right) and a sweep that
confirmed 55 wrong ones. For any other component they are borrowed, and its cuts say so.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .. import geometry as G
from .. import identifiers as I
from ..cutters.deal import Cutter, Gate
from ..ids import Node
from ..pieces import Drawing
from ..schema import Json
from . import filled, skeleton

#: The component whose reviewed cuts set the limits.
CALIBRATED_ON = "山"


@dataclass(frozen=True)
class Reading:
    """One check's reading of one cut: the value to four decimals, the limit it has to stay
    under, the glyph compared with, and whether the unrounded value stayed under."""

    value: float
    limit: float
    against: str
    passes: bool


def _reading(value: float, limit: float, against: str) -> Reading:
    return Reading(round(value, 4), limit, against, not value >= limit)


@dataclass(frozen=True)
class Reference:
    """A component drawn alone in one font, prepared for both checks."""

    glyph: str
    mask: G.Array
    line: G.Array


def references(drawings: Sequence[Drawing], selector: str) -> list[Reference]:
    """The component in every font that draws it alone, in the order of the chain."""
    found = []
    for drawing in drawings:
        key = ("gate", selector)
        if key not in drawing.kept:
            glyph = drawing.glyph(selector)
            if glyph is None or not glyph.pieces:
                drawing.kept[key] = None
            else:
                ink = G.union_of(glyph.pieces)
                drawing.kept[key] = Reference(f"{drawing.id}/{selector}", filled.mask(ink), skeleton.line(ink))
        if drawing.kept[key] is not None:
            found.append(drawing.kept[key])
    return found


def check(ink: G.Path, against: Sequence[Reference]) -> dict[str, Reading]:
    """Both checks of one cut's ink. The skeleton check charges only for centre line the cut adds;
    the filled check for any difference of figure."""
    line = skeleton.line(ink)
    away, glyph = min((skeleton.away(line, reference.line), reference.glyph) for reference in against)
    mask = filled.mask(ink)
    apart, other = min((1 - filled.iou(mask, reference.mask), reference.glyph) for reference in against)
    return {
        "skeleton": _reading(away, skeleton.LIMIT, glyph),
        "filled": _reading(apart, filled.LIMIT, other),
    }


def gate(glyph_of: Callable[[str], str | None], only: str | None = None) -> Gate:
    """Both checks as the dealing cutter asks for them: for each leaf that a font of the chain
    draws alone, or for the leaves that are `only`."""

    def run(cutter: Cutter, node: Node, group: Sequence[int]) -> tuple[Json, str | bool] | None:
        char = glyph_of(node.text)
        if char is None or (only is not None and char != only):
            return None
        against = references(cutter.drawings, f"U+{ord(char):04X}")
        if not against:
            return None
        found = check(G.union_of([cutter.pieces[index] for index in group]), against)
        records = {
            name: {"value": row.value, "limit": row.limit, "against": row.against, "pass": row.passes}
            for name, row in found.items()
        }
        return records, I.component_of(char) if char == CALIBRATED_ON else False

    return run
