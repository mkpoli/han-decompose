"""The `kage` cutter: the division GlyphWiki drew.

A GlyphWiki glyph whose data is a list of type-99 lines places one component glyph per line, and
the engine expands each line into a range of strokes. A placement therefore owns the contours of
its strokes exactly, and a reading under a candidate structure is a matter of pairing the
structure's operands with the placements at the top level of the drawing:

- by count: as many placements as operands, the strokes of the placements being all the strokes
  of the level (a drawing with strokes of its own beside its placements is not a division);
- by layout: the placements lie as the operator says, in the order of the data or, for a row or a
  stack, in the order of their ink;
- by class: the placed glyph's name starts with the code point of the operand.

A leaf whose placement itself places components is opened into its own description where one of
the character's descriptions fits the same way. The cuts are the placements' contours as drawn,
the division is `source`, and the style of a cut is the placed glyph.

A glyph that places nothing is drawn from strokes alone and has no division; a name with no
code point (`cdp-…`, `koseki-…`) is paired with nothing.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import pairwise

from .. import glyphwiki as gw
from .. import identifiers as I
from ..descriptions import Description, Table
from ..glyphwiki import Drawing as Wiki
from ..glyphwiki import Placement
from ..ids import Node, leaves, walk
from ..pieces import Glyph
from ..schema import Json
from . import reading
from .deal import CLOSED, ROWS, STACKS, Skipped, count, ordered, runs, wraps

#: How many components deep a leaf may be opened.
MAX_LEVELS = 6
#: GlyphWiki's frame is 200 units on a 1000-unit em, y down.
SCALE = 5.0


def same_class(operand: int, placed: int) -> bool:
    """Whether a placed glyph's code point is the operand's, or a member of its class.

    The class rows are not read yet (`review/classes.tsv` holds one hand-made row and the builder
    of the corpus rows is not in this checkout), so a class is its one code point."""
    return operand == placed


@dataclass(frozen=True)
class Found:
    """One cut found: its path from the root of the tree and its contours."""

    path: tuple[int, ...]
    contours: list[int]
    placement: Placement | None
    """The glyph GlyphWiki placed for the cut, None where several placements stand for the operand."""


class Division:
    """A GlyphWiki drawing read as a tree of placements."""

    def __init__(self, drawing: Wiki):
        self.drawing = drawing
        self._children: dict[int | None, list[Placement]] = {}
        for placement in drawing.placements:
            self._children.setdefault(placement.parent, []).append(placement)

    def children(self, parent: int | None) -> list[Placement]:
        return self._children.get(parent, [])

    def level(self, parent: int | None) -> tuple[list[Placement], set[int]]:
        """The placements of one level and the strokes the level draws. A level that is one
        placement of everything, with components of its own, is an alias or a wrapper: the level
        is that placement's."""
        strokes = (
            set(range(len(self.drawing.strokes))) if parent is None else set(self.drawing.placements[parent].strokes)
        )
        placed = self.children(parent)
        while len(placed) == 1 and self.children(placed[0].id) and set(placed[0].strokes) == strokes:
            placed = self.children(placed[0].id)
        return placed, strokes

    @property
    def blank(self) -> bool:
        """Whether the drawing places nothing, or places one glyph that draws strokes alone."""
        placed, _ = self.level(None)
        return not placed or (len(placed) == 1 and not self.children(placed[0].id))


@dataclass(frozen=True)
class Unit:
    """The placements that stand for one operand: one, or a run of them where the structure keeps
    together what GlyphWiki placed apart (射 is placed as 身 and 寸)."""

    placed: tuple[Placement, ...]

    @property
    def strokes(self) -> set[int]:
        return {s for p in self.placed for s in p.strokes}

    @property
    def contours(self) -> list[int]:
        return sorted(c for p in self.placed for c in p.contours)

    @property
    def names(self) -> str:
        return ", ".join(p.glyph for p in self.placed)

    @property
    def ink(self) -> tuple[float, float, float, float] | None:
        """The ink of the placements on the 1000-unit em, y up."""
        boxes = [p.ink for p in self.placed if p.ink is not None]
        if not boxes:
            return None
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        return (x0 * SCALE, (200 - y1) * SCALE, x1 * SCALE, (200 - y0) * SCALE)


def _code_point(text: str) -> int | None:
    """The code point of an operand that is a character, with or without a variation selector."""
    try:
        kind, value = I.split_component(I.component_of(text))
    except ValueError:
        return None
    return int(value.split(".")[0], 16) if kind == "u" else None


def _orders(operator: str | None, placed: Sequence[Placement]) -> list[list[Placement]]:
    """The orders to try the placements in: the data's, and the order of the ink along the axis
    of a row or a stack, or the reverse of an enclosure's two."""
    data = list(placed)

    def centre(p: Placement, axis: int) -> float:
        box = Unit((p,)).ink
        return 0.0 if box is None else box[axis] + box[axis + 2]

    if operator in ROWS:
        by = sorted(placed, key=lambda p: centre(p, 0))
    elif operator in STACKS:
        by = sorted(placed, key=lambda p: -centre(p, 1))
    elif operator in CLOSED and len(placed) == 2:
        by = data[::-1]
    else:
        return [data]
    return [data] if by == data else [data, by]


def _lies(operator: str | None, units: Sequence[Unit]) -> str | None:
    """None where the operands lie as the operator says, else what does not."""
    boxes = [unit.ink for unit in units]
    if any(box is None for box in boxes):
        return "a placed component draws nothing"
    real = [box for box in boxes if box is not None]
    if operator in ROWS or operator in STACKS:
        axis = "x" if operator in ROWS else "y"
        for (first, a), (second, b) in pairwise(zip(units, real, strict=True)):
            if not ordered(a, b, axis):
                way = "left to right" if axis == "x" else "top to bottom"
                return f"{first.names} and {second.names} do not follow each other {way}"
        return None
    sides = CLOSED.get(operator or "")
    if sides and not wraps(real[0], real[1], sides):
        return f"{units[0].names} does not enclose {units[1].names}"
    return None


#: How many placements one level may hold and still be grouped into operands.
MOST_PLACED = 12


@dataclass
class Fit:
    """The state of one attempt: the descriptions that open leaves, and what has been found."""

    division: Division
    tables: Sequence[Table]
    found: list[Found]

    def tree(
        self, node: Node, placed: Sequence[Placement], strokes: set[int], path: tuple[int, ...], trail: tuple[str, ...]
    ) -> Node:
        """The node fitted to the placements of its level: a tree with its leaves paired. Raises
        `Skipped` with the reason where the placements do not fit."""
        drawing = self.division.drawing
        n = len(node.children)
        if node.operator == "㇯":
            raise Skipped(
                "unlike-division", f"{node.text} is what remains of its first operand, which no placement draws"
            )
        if len(placed) < n or len(placed) > MOST_PLACED:
            note = f"; the dump lacks {', '.join(drawing.missing)}" if drawing.missing else ""
            raise Skipped(
                "unlike-division",
                f"{drawing.name} places {count(len(placed), 'component')} ({', '.join(p.glyph for p in placed)}) "
                f"for the {count(n, 'operand')} of {node.text}{note}",
            )
        if {s for p in placed for s in p.strokes} != strokes:
            raise Skipped("unlike-division", f"{drawing.name} draws strokes of its own beside its components")
        best: Skipped | None = None
        for order in _orders(node.operator, placed):
            for option in runs(list(range(len(order))), n):
                try:
                    return self._pair(node, [Unit(tuple(order[i] for i in run)) for run in option], path, trail)
                except Skipped as reason:
                    # A layout that fails after every operand matched is the most that was found.
                    if best is None or (reason.code == "layout-mismatch" and best.code != "layout-mismatch"):
                        best = reason
        assert best is not None
        raise best

    def _pair(self, node: Node, units: Sequence[Unit], path: tuple[int, ...], trail: tuple[str, ...]) -> Node:
        mark = len(self.found)
        try:
            children = [
                self.operand(child, unit, (*path, index), trail)
                for index, (child, unit) in enumerate(zip(node.children, units, strict=True))
            ]
            if message := _lies(node.operator, units):
                raise Skipped("layout-mismatch", f"{node.text}: {message}")
        except Skipped:
            del self.found[mark:]
            raise
        return Node(node.text, node.operator, children, node.opened)

    def operand(self, node: Node, unit: Unit, path: tuple[int, ...], trail: tuple[str, ...]) -> Node:
        """One operand paired with the placements that stand for it."""
        if len(unit.placed) > 1:
            if not node.leaf:
                return self.tree(node, unit.placed, unit.strokes, path, trail)
            self.found.append(Found(path, unit.contours, None))
            opened = self.open(node, unit.placed, unit.strokes, path, trail)
            if opened is node:
                raise Skipped(
                    "unlike-division", f"{node.text} is placed as {unit.names}, which none of its descriptions fits"
                )
            return opened
        (placement,) = unit.placed
        placed, strokes = self.division.level(placement.id)
        if not node.leaf:
            if not placed:
                raise Skipped(
                    "unlike-division", f"{node.text} has operands of its own but {placement.glyph} draws strokes alone"
                )
            return self.tree(node, placed, strokes, path, trail)
        wanted = _code_point(node.text)
        info = gw.name_info(placement.glyph)
        if wanted is None:
            raise Skipped("unlike-division", f"{node.text} is no character, and {placement.glyph} is named for one")
        if info is None or not same_class(wanted, info.code_point):
            raise Skipped("unlike-division", f"{node.text} is placed as {placement.glyph}")
        self.found.append(Found(path, list(placement.contours), placement))
        return self.open(node, placed, strokes, path, trail)

    def open(
        self, node: Node, placed: Sequence[Placement], strokes: set[int], path: tuple[int, ...], trail: tuple[str, ...]
    ) -> Node:
        """A leaf opened into the first description of its character that fits the placements
        inside its own; the leaf as it is where none does."""
        char = character(self.tables, node.text)
        if not placed or char is None or char in trail or len(trail) >= MAX_LEVELS:
            return node
        for description in candidates(self.tables, char):
            try:
                inside = description.tree()
            except ValueError:
                continue
            if inside.leaf:
                continue
            mark = len(self.found)
            try:
                fitted = self.tree(inside, placed, strokes, path, (*trail, char))
            except Skipped:
                del self.found[mark:]
                continue
            return Node(node.text, fitted.operator, fitted.children, opened=description.structure)
        return node


def style(font: str, placement: Placement) -> Json:
    """The form a cut was drawn as, read off the glyph GlyphWiki placed."""
    info = gw.name_info(placement.glyph)
    assert info is not None
    member = f"{info.code_point:04X}" + (f".{info.selector:04X}" if info.selector else "")
    out: Json = {"member": I.component("u", member), "basis": "kage", "tier": "source"}
    try:
        out["glyph"] = I.glyph_id(font, I.name_selector(placement.glyph))
    except ValueError:
        pass
    return out


def character(tables: Sequence[Table], text: str) -> str | None:
    """The character a component is drawn as alone, by the first source that knows it."""
    return next((found for table in tables if (found := table.glyph(text)) is not None), None)


def candidates(tables: Sequence[Table], char: str) -> list[Description]:
    """The descriptions of a character in the order of the sources, each structure once."""
    seen: set[str] = set()
    out = []
    for table in tables:
        for description in table.of(char):
            if description.structure not in seen:
                seen.add(description.structure)
                out.append(description)
    return out


def read(glyph: Glyph, division: Division, description: Description, tables: Sequence[Table], font: str) -> list[Json]:
    """The readings of a glyph under one description: its own, and one for each leaf opened.

    Raises `Skipped` where GlyphWiki's placements do not fit the description, and ValueError
    where the description does not read."""
    if division.blank:
        if division.drawing.missing:
            raise Skipped(
                "unlike-division",
                f"{division.drawing.name} places {', '.join(division.drawing.missing)}, which the dump lacks",
            )
        raise Skipped("no-division", f"{division.drawing.name} is drawn from strokes alone")
    root = description.tree()
    for leaf in leaves(root):
        try:
            I.component_of(leaf.text)
        except ValueError as error:
            raise Skipped("unnamed-component", f"{error}") from error
    placed, strokes = division.level(None)
    fit = Fit(division, tables, [])
    tree = fit.tree(root, placed, strokes, (), (description.subject[0],))
    nodes = dict(walk(tree))
    held = {found.path: found.contours for found in fit.found}
    cuts: list[Json] = []
    for found in fit.found:
        more: Json = {} if found.placement is None else {"style": style(font, found.placement)}
        if found.path:
            more["frame"] = reading.frame(
                glyph, [c for other, c in held.items() if other[: len(found.path) - 1] == found.path[:-1]]
            )
        cuts.append(
            reading.cut(
                glyph,
                description,
                tree,
                found.path,
                nodes[found.path],
                held[found.path],
                "accepted",
                "kage",
                "source",
                **more,
            )
        )
    return reading.reading(glyph, description, tree, "kage", "contour", cuts)


def with_subject(description: Description, subject: str) -> Description:
    """The description of a variation sequence: the same structure, read for the sequence."""
    return replace(description, subject=subject)


@dataclass
class Outcome:
    """What reading one glyph gave under each candidate structure."""

    readings: list[Json]
    skipped: list[Json]


def cut_glyph(
    font: str, selector: str, name: str, glyph: Glyph, division: Division, tables: Sequence[Table]
) -> Outcome:
    """A GlyphWiki glyph read under every candidate structure of its character."""
    info = gw.name_info(name)
    out = Outcome([], [])
    if info is None:
        return out
    char = chr(info.code_point)
    subject = char + (chr(info.selector) if info.selector and selector.startswith("U+") else "")
    glyph_id = I.glyph_id(font, selector)
    for description in candidates(tables, char):
        description = with_subject(description, subject)
        try:
            if description.tree().leaf:
                continue
            out.readings.extend(read(glyph, division, description, tables, font))
        except Skipped as reason:
            out.skipped.append(reading.skipped(description, reason.code, reason.text, glyph_id))
        except (ValueError, RecursionError) as error:
            code, text = (
                reading.unreadable(error)
                if isinstance(error, ValueError)
                else ("unreadable-description", f"the description does not read: {error}")
            )
            out.skipped.append(reading.skipped(description, code, text, glyph_id))
    return out
