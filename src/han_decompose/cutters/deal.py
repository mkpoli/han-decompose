"""Deal a glyph's pieces out to the components of its description.

No boundary is invented: the pieces are the font's own, and the one question asked at each node of
a description is which pieces fall to which operand. The operands of a row or a stack follow each
other, so the pieces are sorted along that axis and only the divisions that keep the order are
tried; the operands of an enclosure or an overlay share each other's extent, so every way of
dealing the pieces out is tried, less those that put the enclosing operand inside the other.

A division is judged by shape. Each group of pieces is fingerprinted (its ink as coverage over a
grid on its own box) and compared with the component it would belong to as a font draws that
component alone. Scaling to the box is what lets 山 squashed under another component be
recognised as 山. The division whose groups agree best wins, and it has to win by a margin.
"""

from collections.abc import Callable, Sequence
from itertools import pairwise
from typing import Literal

import numpy as np
import pathops

from .. import geometry as G
from ..descriptions import Description
from ..ids import Node, leaves, walk
from ..pieces import Drawing, Glyph
from ..schema import Json
from . import reading

#: Cells across the square a shape is fingerprinted on, and samples per cell.
GRID = 16
SUBSAMPLE = 4
#: A group of pieces looks at least this much like the component claiming it. The floor only
#: rejects nonsense; the same component squashed into a stack never scores near 1.
MIN_LIKENESS = 0.30
#: The winning division beats the next one by this much.
MIN_MARGIN = 0.015
#: Slack on each side, in units, for a boundary two components share.
REACH = 12.0
#: The most divisions tried at an enclosure or an overlay.
MOST_DEALS = 4096

#: The sides an enclosure closes around what it holds. ⿻ overlays its operands and closes nothing.
CLOSED: dict[str, tuple[str, ...]] = {
    "⿴": ("top", "bottom", "left", "right"),
    "⿵": ("top", "left", "right"),
    "⿶": ("bottom", "left", "right"),
    "⿷": ("top", "bottom", "left"),
    "⿼": ("top", "bottom", "right"),
    "⿸": ("top", "left"),
    "⿹": ("top", "right"),
    "⿺": ("bottom", "left"),
    "⿽": ("bottom", "right"),
}
STACKS = ("⿱", "⿳")
ROWS = ("⿰", "⿲")


#: What a leaf opens into: the node and the components opened above it give a node with the
#: component's own operator and operands, or None to leave the leaf whole.
Opener = Callable[[Node, Sequence[str]], Node | None]


class Skipped(Exception):
    """A glyph that cannot be accounted for, with the reason as a code of the format and a
    sentence."""

    def __init__(self, code: str, text: str):
        super().__init__(text)
        self.code, self.text = code, text


def count(number: int, thing: str) -> str:
    """`1 piece`, `2 pieces`."""
    return f"{number} {thing}" + ("" if number == 1 else "s")


def fingerprint(edges: G.Array, box: G.Box) -> G.Array:
    """How much ink sits in each cell of a square grid over a box, as coverage fractions: a
    component is drawn with heavier strokes when it is squashed, and coverage survives that where
    a silhouette does not."""
    return G.coverage(edges, box, GRID, SUBSAMPLE).ravel()


def likeness(left: G.Array, right: G.Array) -> float:
    """Agreement between two fingerprints, 1 for the same ink everywhere."""
    total = float(np.maximum(left, right).sum())
    return float(np.minimum(left, right).sum()) / total if total else 0.0


def standing(drawing: Drawing, selector: str) -> G.Array | None:
    """The fingerprint of a glyph as a font draws it alone, on its own box."""
    key = ("whole", selector)
    if key not in drawing.kept:
        glyph = drawing.glyph(selector)
        drawing.kept[key] = (
            fingerprint(np.concatenate([glyph.edges(i) for i in range(len(glyph.pieces))]), G.box_of(glyph.pieces))
            if glyph is not None and glyph.pieces
            else None
        )
    found: G.Array | None = drawing.kept[key]
    return found


def runs(pieces: Sequence[int], parts: int) -> list[list[list[int]]]:
    """Every way to cut an ordered list of pieces into `parts` runs, none empty."""
    if parts == 1:
        return [[list(pieces)]]
    out = []
    for cut in range(1, len(pieces) - parts + 2):
        for rest in runs(pieces[cut:], parts - 1):
            out.append([list(pieces[:cut]), *rest])
    return out


def spreads(pieces: Sequence[int], parts: int) -> list[list[list[int]]]:
    """Every way to deal an unordered list of pieces into `parts` groups, none empty."""
    if parts == 1:
        return [[list(pieces)]]
    out = []
    for mask in range(1, 1 << len(pieces)):
        head = [piece for index, piece in enumerate(pieces) if mask >> index & 1]
        tail = [piece for index, piece in enumerate(pieces) if not mask >> index & 1]
        if len(tail) < parts - 1:
            continue
        for rest in spreads(tail, parts - 1):
            out.append([head, *rest])
    return out


def wraps(outer: G.Box, inner: G.Box, sides: Sequence[str]) -> bool:
    """Whether one extent closes around another on the sides the operator closes. On the sides it
    leaves open the held component runs out past the other, so nothing is asked there."""
    for side in sides:
        if side == "top" and outer[3] < inner[3] - REACH:
            return False
        if side == "bottom" and outer[1] > inner[1] + REACH:
            return False
        if side == "left" and outer[0] > inner[0] + REACH:
            return False
        if side == "right" and outer[2] < inner[2] - REACH:
            return False
    return True


def ordered(first: G.Box, second: G.Box, axis: str) -> bool:
    """Whether two extents follow each other along the axis the operator runs on: the earlier one
    starts and ends earlier, and neither stands in the other's span. Ends are compared, because
    real glyphs interlock without either component taking the other's place."""
    low, high = (1, 3) if axis == "y" else (0, 2)
    if axis == "y":
        if first[1] <= second[1] - REACH or first[3] <= second[3] - REACH:
            return False
    elif first[0] >= second[0] + REACH or first[2] >= second[2] + REACH:
        return False
    overlap = min(first[high], second[high]) - max(first[low], second[low])
    narrower = min(first[high] - first[low], second[high] - second[low])
    return overlap < 0.5 * narrower if narrower > 0 else True


class Cutter:
    """Deals one glyph's pieces to the nodes of a description.

    `drawings` are the fonts a component is looked for in, the glyph's own first. `glyph_of` gives
    the character a component is drawn as alone, or None for one that has no glyph.
    """

    def __init__(self, glyph: Glyph, drawings: Sequence[Drawing], glyph_of: Callable[[str], str | None]):
        if not drawings or drawings[0].id != glyph.font:
            raise ValueError(f"The fonts a component is looked for in start with the glyph's own, {glyph.font}.")
        self.glyph, self.drawings, self.glyph_of = glyph, drawings, glyph_of
        self.pieces = glyph.pieces
        self._prints: dict[tuple[int, ...], G.Array] = {}
        self._boxes: dict[tuple[int, ...], G.Box] = {}
        #: The weakest agreement at each node dealt, and the margin it was won by.
        self.marks: list[float] = []
        self.margins: list[float] = []

    def group_print(self, group: Sequence[int]) -> G.Array:
        key = tuple(sorted(group))
        if key not in self._prints:
            edges = np.concatenate([self.glyph.edges(index) for index in key])
            self._prints[key] = fingerprint(edges, G.box_of([self.pieces[index] for index in key]))
        return self._prints[key]

    def extent(self, group: Sequence[int]) -> G.Box:
        """The box of a group's ink once its pieces are merged."""
        key = tuple(sorted(group))
        if key not in self._boxes:
            box: G.Box = G.union_of([self.pieces[index] for index in key]).bounds
            self._boxes[key] = box
        return self._boxes[key]

    def template(self, text: str) -> tuple[G.Array, bool, Drawing] | None:
        """A component as it is drawn alone, from the first font that has it, and whether that is
        the glyph's own font. A drawing borrowed from another font ranks the divisions without
        being held to the floor: how closely two fonts agree about one component is not a thing
        to hold a font to."""
        char = self.glyph_of(text)
        if char is None:
            return None
        selector = f"U+{ord(char):04X}"
        for index, drawing in enumerate(self.drawings):
            shape = standing(drawing, selector)
            if shape is not None:
                return shape, index == 0, drawing
        return None

    def agreement(self, node: Node, group: Sequence[int]) -> tuple[float, bool] | None:
        """How much a group of pieces looks like the component it is offered to, and whether the
        glyph's own font drew the comparison. None where no font has a glyph for the component;
        its operands are then judged a level down."""
        found = self.template(node.text)
        if found is None:
            return None
        return likeness(self.group_print(group), found[0]), found[1]

    def candidates(self, node: Node, group: Sequence[int]) -> list[list[list[int]]]:
        """The divisions of a node's pieces among its operands that lie as its operator says."""
        arity = len(node.children)
        if node.operator in STACKS or node.operator in ROWS:
            if node.operator in STACKS:
                # Where two pieces sit at the same height, the leftmost reads first.
                axis = "y"
                order = sorted(group, key=lambda i: (-sum(self.pieces[i].bounds[1::2]), self.pieces[i].bounds[0]))
            else:
                axis = "x"
                order = sorted(group, key=lambda i: (sum(self.pieces[i].bounds[0::2]), -self.pieces[i].bounds[3]))
            kept = [
                option
                for option in runs(order, arity)
                if all(ordered(self.extent(first), self.extent(second), axis) for first, second in pairwise(option))
            ]
            if not kept and len(group) >= arity:
                raise Skipped(
                    "layout-mismatch", f"no division of {node.text} lays its operands out the way {node.operator} reads"
                )
            return kept
        if arity ** len(group) > MOST_DEALS:
            raise Skipped("too-many-pieces", f"{node.text} covers {count(len(group), 'piece')}, too many to deal out")
        offered = spreads(group, arity)
        sides = CLOSED.get(node.operator or "")
        if not sides:
            return offered
        kept = [option for option in offered if wraps(self.extent(option[0]), self.extent(option[1]), sides)]
        if not kept and offered:
            raise Skipped(
                "no-enclosure",
                f"no division of {node.text} puts {node.children[0].text} around {node.children[1].text}",
            )
        return kept

    def best(self, node: Node, group: Sequence[int]) -> list[list[int]]:
        """The division of a node's pieces among its operands that agrees best with them."""
        candidates = self.candidates(node, group)
        if not candidates:
            raise Skipped("too-few-pieces", f"{node.text} has fewer pieces than operands")
        unknown = [child.text for child in node.children if self.template(child.text) is None]
        if len(unknown) > 1:
            raise Skipped(
                "no-reference-glyph",
                f"two operands of {node.text} have no glyph to be recognised by: {', '.join(unknown)}",
            )
        # The floor is held against the components the glyph's own font also draws. Where it draws
        # none of them, the floor falls to all of them. What is recorded is the weakest agreement
        # of all, borrowed or not.
        scored = []
        for option in candidates:
            marks = [self.agreement(child, part) for child, part in zip(node.children, option, strict=True)]
            known = [mark for mark in marks if mark is not None]
            if not known:
                raise Skipped("no-reference-glyph", f"no glyph to recognise the operands of {node.text} by")
            held = [mark for mark, own in known if own] or [mark for mark, _ in known]
            scored.append(
                (sum(mark for mark, _ in known) / len(known), min(held), min(mark for mark, _ in known), option)
            )
        scored.sort(key=lambda row: -row[0])
        total, lowest, weakest, option = scored[0]
        if lowest < MIN_LIKENESS:
            raise Skipped(
                "unlike-element", f"a group of pieces does not look like its element in {node.text} ({lowest:.2f})"
            )
        if len(scored) > 1 and total - scored[1][0] < MIN_MARGIN:
            raise Skipped("ambiguous", f"two readings of {node.text} fit the pieces equally well")
        self.marks.append(weakest)
        if len(scored) > 1:
            self.margins.append(total - scored[1][0])
        return option

    def cut(
        self, node: Node, group: Sequence[int], opener: Opener | None = None, trail: tuple[str, ...] = ()
    ) -> list[tuple[Node, list[int]]]:
        """Every leaf of a description with the pieces that belong to it.

        With an `opener`, a leaf of several pieces is opened into its component's own description
        where those pieces can be dealt to its operands, and its operands are cut in turn; a leaf
        whose pieces cannot be dealt stays whole. `trail` holds the components opened above."""
        if not group:
            raise Skipped("too-few-pieces", f"no pieces left for {node.text}")
        if node.leaf and opener is not None and len(group) > 1:
            inside = opener(node, trail)
            if inside is not None:
                # The opening holds only if the whole of the component's description can be
                # dealt; where any part of it fails, the leaf stays whole and nothing of the
                # attempt is kept.
                marks, margins = len(self.marks), len(self.margins)
                node.operator, node.children, node.opened = inside.operator, inside.children, inside.opened
                try:
                    return self._operands(node, group, opener, (*trail, self.glyph_of(node.text) or node.text))
                except Skipped:
                    node.operator, node.children, node.opened = None, [], None
                    del self.marks[marks:], self.margins[margins:]
        if node.leaf:
            return [(node, list(group))]
        return self._operands(node, group, opener, trail)

    def _operands(
        self, node: Node, group: Sequence[int], opener: Opener | None, trail: tuple[str, ...]
    ) -> list[tuple[Node, list[int]]]:
        out: list[tuple[Node, list[int]]] = []
        for child, part in zip(node.children, self.best(node, group), strict=True):
            out.extend(self.cut(child, part, opener, trail))
        return out


#: A reading drawn again from its components' own glyphs looks at least this much like the glyph.
#: A floor on nonsense: the components come from whatever font draws them, in a style of their own.
MIN_REDRAWN = 0.40


def alone(cutter: Cutter, node: Node) -> tuple[Glyph, Drawing] | None:
    """A component's own glyph, from the font its template came from."""
    found = cutter.template(node.text)
    char = cutter.glyph_of(node.text)
    if found is None or char is None:
        return None
    glyph = found[2].glyph(f"U+{ord(char):04X}")
    return (glyph, found[2]) if glyph is not None else None


def window_count(cutter: Cutter, node: Node, group: Sequence[int]) -> tuple[int, str] | None:
    """How many windows the pieces given to a component enclose, where the component drawn alone
    encloses none, with the glyph it was held against; None where it draws windows of its own or
    has no glyph. Squashing a component closes slivers where its strokes cross, but a window, the
    counter of 口 or 田, belongs to a component that draws one: pieces that enclose one for a
    component that has none carry another component's ink."""
    drawn = alone(cutter, node)
    if drawn is None or G.windows(drawn[0].pieces):
        return None
    return G.windows([cutter.pieces[index] for index in group]), f"{drawn[1].id}/{drawn[0].selector}"


def redrawn(cutter: Cutter, hands: Sequence[tuple[Node, Sequence[int]]]) -> float | None:
    """How much the reading, drawn again, looks like the glyph: each component as a font draws it
    alone is put in the box its pieces occupy. None where a component has no glyph to draw."""
    composite: list[G.Path] = []
    for node, group in hands:
        drawn = alone(cutter, node)
        if drawn is None:
            return None
        composite.extend(G.scaled(drawn[0].pieces, G.box_of([cutter.pieces[index] for index in group])))
    box = G.box_of(cutter.pieces)
    again = fingerprint(np.concatenate([G.edges_of(path) for path in composite]), box)
    glyph = fingerprint(np.concatenate([cutter.glyph.edges(index) for index in range(len(cutter.pieces))]), box)
    return likeness(again, glyph)


#: Checks of one leaf beyond the cutter's own: the node and its pieces give the check records, and
#: the component whose reviewed cuts set the limits of those checks, or False.
Gate = Callable[["Cutter", Node, Sequence[int]], tuple[Json, str | Literal[False]] | None]


def cutter_for(glyph: Glyph, drawings: Sequence[Drawing], root: Node, glyph_of: Callable[[str], str | None]) -> Cutter:
    """A cutter for a glyph that can be dealt out to a tree at all."""
    if not glyph.pieces:
        raise Skipped("no-ink", "the glyph draws no ink")
    if not glyph.tiles:
        raise Skipped("does-not-tile", "the pieces do not add up to the glyph the font draws")
    if len(glyph.pieces) < len(leaves(root)):
        raise Skipped(
            "too-few-pieces",
            f"the glyph draws {count(len(glyph.pieces), 'piece')} for {count(len(leaves(root)), 'element')}",
        )
    return Cutter(glyph, drawings, glyph_of)


def read(
    glyph: Glyph,
    drawings: Sequence[Drawing],
    description: Description,
    root: Node,
    glyph_of: Callable[[str], str | None],
    whole: bool = True,
    gate: Gate | None = None,
    opener: Opener | None = None,
) -> Json:
    """One glyph read under a tree: every leaf with the contours dealt to it.

    With `whole`, the reading is held against the glyph: a leaf may not enclose a window its
    component never draws, and the reading drawn again has to look like the glyph. With an `opener`
    a leaf is opened into its component's own description where its pieces allow. `gate` adds
    checks of single leaves. A cut that fails a check is kept and marked refused.
    """
    cutter = cutter_for(glyph, drawings, root, glyph_of)
    try:
        subject = glyph_of(description.subject) or description.subject
        hands = cutter.cut(root, list(range(len(glyph.pieces))), opener, (subject,))
    except pathops.PathOpsError as error:
        raise Skipped("does-not-tile", "the outlines of a group of pieces could not be merged") from error
    evidence: Json = {}
    if cutter.marks:
        evidence["likeness"] = reading.number(min(cutter.marks), 4)
    if cutter.margins:
        evidence["margin"] = reading.number(min(cutter.margins), 4)
    if whole:
        again = redrawn(cutter, hands)
        if again is not None:
            if again < MIN_REDRAWN:
                raise Skipped(
                    "unlike-whole",
                    f"the elements, each drawn where its pieces sit, do not come out as the character ({again:.2f})",
                )
            evidence["redrawn"] = reading.number(again, 4)
    paths = {id(node): path for path, node in walk(root)}
    held = {paths[id(node)]: glyph.contours_of(group) for node, group in hands}
    cuts = []
    for node, group in hands:
        path = paths[id(node)]
        more: Json = {"area": reading.number(sum(abs(glyph.pieces[index].area) for index in group), 2)}
        if path:
            under = [indices for other, indices in held.items() if other[: len(path) - 1] == path[:-1]]
            more["frame"] = reading.frame(glyph, under)
        checks: Json = {}
        calibrated: str | Literal[False] = False
        mark = cutter.agreement(node, group)
        if mark is not None:
            more["evidence"] = {"fit": reading.number(mark[0], 4)}
        if whole:
            found = window_count(cutter, node, group)
            if found is not None:
                checks["windows"] = {"value": found[0], "limit": 1, "against": found[1], "pass": found[0] < 1}
        if gate is not None:
            added = gate(cutter, node, group)
            if added is not None:
                checks.update(added[0])
                calibrated = added[1]
        if checks:
            more["checks"] = checks
            more["calibrated"] = calibrated
        status = "accepted" if all(check["pass"] for check in checks.values()) else "refused"
        cuts.append(reading.cut(glyph, description, root, path, node, held[path], status, **more))
    return reading.reading(glyph, description, root, "deal", "piece", cuts, evidence)
