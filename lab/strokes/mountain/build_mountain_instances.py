# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["fonttools[woff]==4.63.0", "brotli==1.2.0", "skia-pathops==0.9.2",
#                 "numpy==2.1.3"]
# ///
"""Cut the 山 out of every Han character whose decomposition reaches one.

A character written with 山 in it is drawn, in the font, as a set of closed
outlines that do not touch each other, and each of those pieces belongs whole to
one element of the description. So the 山 can be lifted out along ink the font
already draws, and the only question is which pieces are the 山. That question is
answered by scripts/build_donor_parts.py, whose cutter deals a glyph's pieces out
to the operands of its description and settles each hand by fingerprinting it
against the element it would belong to, drawn alone. This build calls that cutter
and keeps the hand that went to 山.

A description does not always say 山 itself. 仙 is ⿰亻山 and names it; 剛 is ⿰岡刂
and 催 is ⿰亻崔, and the 山 is a level further down, inside 岡 and inside 崔. Both
hold a real 山, so the description is spelled out through the components that
reach one: a leaf whose own description reaches 山 is replaced by that
description, and so on to the bottom. Branches that reach no 山 are left as they
stand, so the cut goes no deeper than the 山 it is after. 剛's tree is then
⿰⿵冂⿰山山刂, and the cut runs outward-in — the left operand of ⿰ first, then
inside 岡 the held operand of ⿵, then the two 山 of the ⿰ inside that — so what
is recorded is the real 山 at its real position and scale, with the path down to
it. For each instance that path is written out twice over: as the operands walked
through, and as the components crossed into, 岡 for 剛 and 崔 for 催.

Every operator is in scope, not only the stacks. The cutter already reads each
operator the way it means — the operands of ⿰ run left to right, those of ⿱ top
to bottom, and the operands of an enclosure, which cover each other's extent, are
offered every way of dealing the pieces out.

For each instance this records the operand 山 is, the operator above it, the path
of operands and of components down to it, the ink as a path on the 1000-unit em,
its bounding box, its area against 山 drawn alone in the same face, and the face.
A character whose account does not close is skipped with the reason, never
guessed at.

Deal the pieces out well and the hand given to 山 is a 山. So every instance is
held against 山 drawn alone, on shape: both are stretched on their own to fill a
64×64 square and compared by 1 − IoU, which reads the figure and not its size.
An instance whose disagreement reaches MAX_DISAGREEMENT is refused and the
reading is written into the skip, because a cut that gives 山 something shaped
unlike 山 has misread the glyph. The character keeps whatever instances pass; one
whose every instance is refused leaves with the reason, and is not re-cut from
another face or a shallower reading to get it back in.

    uv run scripts/build_mountain_instances.py [--only CHARS] [--limit N]

Writes data/mountain-instances.json.gz.

Character shapes: Noto Sans CJK JP 2.004, SIL OFL 1.1 (fonts/OFL-NotoSansCJK.txt),
then Plangothic P1 and P2 V2.9.5795, SIL OFL 1.1, for what Noto leaves out.
Between them the three draw every character the IDS table carries. Descriptions:
BabelStone IDS, Andrew West (data/babelstone-ids.tsv.gz).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import pathops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_donor_parts as base  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# The shape measurement, from the study that settled it: normalising a shape to
# its own box, rasterising it and overlapping two of them all live there, and the
# gate below is the same arithmetic the labelled set was scored with.
sys.path.insert(0, str(ROOT / "analysis" / "mountain-fit"))
import shapes as mountain_shapes  # noqa: E402
# Thinning and the one-sided Chamfer, from the sweep that chose them.
sys.path.insert(0, str(ROOT / "analysis" / "skeleton-fit"))
sys.path.insert(0, str(ROOT / "analysis" / "gate-tune"))
import thin as mountain_thin  # noqa: E402
import variants as mountain_variants  # noqa: E402


TARGET = ROOT / "data" / "mountain-instances.json.gz"

# The faces to draw from, in order of preference, all three sans. Noto Sans CJK
# JP draws the common characters; Plangothic P1 and P2 draw the rest. Over the
# 103,825 characters the IDS table carries, the three leave none undrawn.
FACE_FILES = (
    "NotoSansCJKjp-VF-2.004.ttf",
    "PlangothicP1-Regular-V2.9.5795.ttf",
    "PlangothicP2-Regular-V2.9.5795.ttf",
)

MOUNTAIN = "山"   # the component this run cuts out; --component replaces it

# How many components deep a description may be spelled out. The deepest 山 the
# table holds sits four components down; the ceiling is there to stop a chain of
# descriptions that leads nowhere.
MAX_LEVELS = 8

# What each operand of an operator is called. The enclosure and surround
# operators take the surrounding element first and the surrounded one second,
# which is what ⿴ through ⿺ all mean; ⿻ overlays its operands, so neither of
# them encloses the other and both are the overlay.
POSITIONS: dict[str, tuple[str, ...]] = {
    "⿰": ("left", "right"),
    "⿱": ("top", "bottom"),
    "⿲": ("left", "middle", "right"),
    "⿳": ("top", "middle", "bottom"),
    "⿴": ("enclosing", "inner"),
    "⿵": ("enclosing", "inner"),
    "⿶": ("enclosing", "inner"),
    "⿷": ("enclosing", "inner"),
    "⿸": ("enclosing", "inner"),
    "⿹": ("enclosing", "inner"),
    "⿺": ("enclosing", "inner"),
    "⿼": ("enclosing", "inner"),
    "⿽": ("enclosing", "inner"),
    "⿻": ("overlay", "overlay"),
    "㇯": ("overlay", "overlay"),
    "⿾": ("whole",),
    "⿿": ("whole",),
    "〾": ("whole",),
}


def position_of(operator: str, index: int) -> str:
    names = POSITIONS.get(operator, ())
    return names[index] if index < len(names) else f"operand {index + 1}"


# The sides an enclosure closes around what it holds. ⿵ wraps the top and both
# flanks and opens downwards, ⿸ wraps the top and the left and opens towards the
# bottom right, and so on; ⿻ overlays its operands and closes nothing.
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
# Slack on each side, in glyph units, for a boundary the two elements share.
REACH = 12.0
# How much an instance must look like 山 drawn alone before it is written out.
# The floor is at the bottom on purpose. Every instance is measured against a
# standing 山 and the reading is written out as `fit`, but the measure does not
# sort sound cuts from unsound ones and must not be used as though it did: a
# narrow left-hand 山, which is right, reads 0.33, and so does the one case found
# where the font joins the 山 to its neighbour and a single piece carries both.
# What the number is good for is ranking — the page offers the weakest readings
# first so they can be looked at — and raising it into a gate would throw away
# scores of correct instances to catch a handful of wrong ones.
MIN_FIT = 0.0

# How far an instance may stand from 山 drawn alone, in shape, before the build
# refuses it. The reading is 1 − IoU between two 64×64 rasters, each stretched on
# its own to fill the square, so size and aspect are normalised away and what is
# left is the figure: where the strokes run and what they enclose. An instance is
# measured against 山 as drawn by every pinned face that draws it alone and keeps
# its best reading, so it is only faulted when it looks unlike all of them.
#
# Unlike `fit` below, this one separates the two classes outright. Of the 208
# instances judged by looking at them (analysis/mountain-fit/labels.json, drawn
# from the worst of the ordering, a stratified sample across it, and the worst of
# four other measures) the soundly cut ones reach 0.599 at worst and the badly
# cut ones 0.636 at best, with nothing in between; this cut-off sits in that gap
# and splits the labelled set with no instance on the wrong side.
MAX_DISAGREEMENT = 0.6081
# The grid both shapes are rasterised on, and the resolution the cut-off was
# calibrated at. A finer grid is a different measure and needs its own number.
DISAGREEMENT_GRID = 64


def wraps(outer: tuple[float, ...], inner: tuple[float, ...], sides) -> bool:
    """Does one extent close around another on the sides the operator closes?

    An enclosing element reaches past what it holds on every side it closes. On
    the sides the operator leaves open — the foot of ⿵, the bottom right of ⿸ —
    the held element runs out past it, so nothing is asked there.
    """
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


def ordered(first: tuple[float, ...], second: tuple[float, ...], axis: str) -> bool:
    """Do two extents follow each other along the axis the operator runs on?

    A row's operands run left to right and a stack's top to bottom, so of two
    neighbours the earlier one both starts and ends earlier along that axis, and
    neither stands in the other's column. The ends are compared rather than the
    gap between them, because real glyphs interlock — a left element's foot
    reaches under the right one — without either taking the other's place. What
    is ruled out is one group covering the span the other was to hold, which is
    what happens when the font draws the two joined and a single piece carries
    both.
    """
    low, high = (1, 3) if axis == "y" else (0, 2)
    if axis == "y":
        if first[1] <= second[1] - REACH or first[3] <= second[3] - REACH:
            return False
    elif first[0] >= second[0] + REACH or first[2] >= second[2] + REACH:
        return False
    overlap = min(first[high], second[high]) - max(first[low], second[low])
    narrower = min(first[high] - first[low], second[high] - second[low])
    return overlap < 0.5 * narrower if narrower > 0 else True


class Enclosing(base.Cutter):
    """The donor-parts cutter, with the enclosure operators read as enclosures.

    Those operators are the ones whose operands share each other's extent, so the
    base cutter offers every way of dealing the pieces out and lets the shapes
    decide. Shape alone cannot tell a frame from what sits inside it: a frame and
    its contents each look, normalised to their own box, a little like a squashed
    山, and the reading that hands the frame to 山 sometimes scores higher. But
    the operator has already said which operand is the frame. So the deals that
    contradict it are not offered, and a character with no deal left is skipped
    rather than read inside out.
    """

    def candidates(self, node: base.Node, group: list[int]) -> list[list[list[int]]]:
        arity = len(node.children)
        if node.operator in ("⿱", "⿳", "⿰", "⿲"):
            axis = "y" if node.operator in ("⿱", "⿳") else "x"
            if axis == "y":
                order = sorted(group, key=lambda i: (-sum(self.pieces[i].bounds[1::2]),
                                                     self.pieces[i].bounds[0]))
            else:
                order = sorted(group, key=lambda i: (sum(self.pieces[i].bounds[0::2]),
                                                     -self.pieces[i].bounds[3]))
            offered = base.runs(order, arity)
            kept = [option for option in offered
                    if all(ordered(base.union_of([self.pieces[i] for i in option[at]]).bounds,
                                   base.union_of([self.pieces[i] for i in option[at + 1]]).bounds,
                                   axis)
                           for at in range(arity - 1))]
            if not kept:
                raise base.Skipped(f"no division of {node.text} lays its operands out "
                                   f"the way {node.operator} reads")
            return kept
        if arity ** len(group) > 4096:
            raise base.Skipped(f"{node.text} covers {base.count(len(group), 'piece')}, "
                               f"too many to deal out")
        offered = base.spreads(group, arity)
        sides = CLOSED.get(node.operator or "")
        if not sides:
            return offered
        kept = [option for option in offered
                if wraps(base.union_of([self.pieces[i] for i in option[0]]).bounds,
                         base.union_of([self.pieces[i] for i in option[1]]).bounds, sides)]
        if not kept:
            raise base.Skipped(
                f"no division of {node.text} puts {node.children[0].text} around "
                f"{node.children[1].text}")
        return kept

    def best(self, node: base.Node, group: list[int]) -> list[list[int]]:
        candidates = self.candidates(node, group)
        if not candidates:
            raise base.Skipped(f"{node.text} has fewer pieces than operands")
        unknown = [child.text for child in node.children
                   if self.agreement(child, group) is None]
        if len(unknown) > 1:
            raise base.Skipped(f"two operands of {node.text} have no glyph to be recognised by: "
                               f"{', '.join(unknown)}")
        scored = []
        for option in candidates:
            marks = [self.agreement(child, part)
                     for child, part in zip(node.children, option)]
            known = [mark for mark in marks if mark is not None]
            if not known:
                raise base.Skipped(f"no glyph to recognise the operands of {node.text} by")
            held = [mark for mark, own in known if own] or [mark for mark, _ in known]
            scored.append((sum(mark for mark, _ in known) / len(known), min(held),
                           min(mark for mark, _ in known), option))
        scored.sort(key=lambda row: -row[0])
        total, lowest, weakest, option = scored[0]
        if lowest < base.MIN_LIKENESS:
            raise base.Skipped(
                f"a group of pieces does not look like its element in {node.text} "
                f"({lowest:.2f})")
        if len(scored) > 1 and total - scored[1][0] < base.MIN_MARGIN:
            raise base.Skipped(f"two readings of {node.text} fit the pieces equally well")
        self.marks.append(weakest)
        return option


def description_of(glyph: str, table: dict[str, list[str]]) -> base.Node | None:
    """A character's own description as a tree, or None where it has none.

    Nothing is left to say where the table writes a character as itself, carries
    no operator for it, or does not carry it at all.
    """
    if len(glyph) != 1 or glyph not in table:
        return None
    ids = table[glyph][0]
    if ids == glyph or not any(token in base.ARITY for token in ids):
        return None
    try:
        return base.parse(ids)
    except ValueError:
        return None


def holders(table: dict[str, list[str]], labels: dict[str, str]) -> set[str]:
    """Every character a 山 reaches up into, however deep it sits.

    Read the other way round, so the answer is exact and a description that
    leads back into itself cannot loop: each leaf of each description is an edge
    from the component to the character written with it, and a character holds a
    山 if 山 reaches it along those edges. One walk up from 山 answers the whole
    table at once.
    """
    users: dict[str, list[str]] = {}
    for char in table:
        root = description_of(char, table)
        if root is None:
            continue
        for leaf in base.terminals(root):
            glyph = base.glyph_of(leaf.text, labels)
            if glyph and glyph != char:
                users.setdefault(glyph, []).append(char)
    found: set[str] = set()
    queue = [MOUNTAIN]
    while queue:
        for char in users.get(queue.pop(), ()):
            if char not in found:
                found.add(char)
                queue.append(char)
    return found - {MOUNTAIN}


def grown(node: base.Node, table: dict[str, list[str]], labels: dict[str, str],
          holds: set[str], seen: frozenset[str], cap: int) -> base.Node:
    """A description spelled out through the components that reach 山.

    A leaf is replaced by its own description only where that component holds a
    山; a branch that holds none stays the leaf it was, so the cut goes no deeper
    than the 山 it is after rather than walking every component to the bottom.
    The substituted node keeps the component's own text, so the cutter still
    recognises its pieces by the glyph the font draws for it.

    `cap` is how many components deep the spelling out may go. At 0 nothing is
    opened and the tree is the character's own description, which is the reading
    a 山 the description names itself needs.
    """
    if not node.leaf:
        return base.Node(node.text, node.operator,
                         [grown(child, table, labels, holds, seen, cap)
                          for child in node.children])
    glyph = base.glyph_of(node.text, labels)
    if len(seen) > cap or glyph not in holds or glyph in seen:
        return node
    root = description_of(glyph, table)
    if root is None:
        return node
    inside = grown(root, table, labels, holds, seen | {glyph}, cap)
    return base.Node(node.text, inside.operator, inside.children)


def readings(char: str, ids: str, table: dict[str, list[str]], labels: dict[str, str],
             holds: set[str]) -> list[tuple[int, base.Node]]:
    """The trees to try for one character, the fullest spelling out first.

    The fullest reading is the one to want: it reaches every 山 the character
    holds. But a component the font draws joined to its neighbour cannot be
    opened, and a reading that fails over one such component would otherwise
    take the 山 the character names outright down with it. So the spelling out
    is offered at every depth, deepest first, down to the shallowest that still
    reaches a 山 — and a character keeps the instances the deepest reading that
    holds can give it, with the depth it settled at recorded.
    """
    offered, last = [], None
    for cap in range(MAX_LEVELS + 1):
        root = grown(base.parse(ids), table, labels, holds, frozenset({char}), cap)
        text = spelled(root)
        if text == last:
            break
        last = text
        if any(base.glyph_of(node.text, labels) == MOUNTAIN for node in base.terminals(root)):
            offered.append((cap, root))
    return offered[::-1]


def spelled(node: base.Node) -> str:
    """A grown tree written back out as one IDS, components spelled out."""
    if node.leaf:
        return node.text
    return (node.operator or "") + "".join(spelled(child) for child in node.children)


def opened_in(root: base.Node, labels: dict[str, str]) -> set[int]:
    """The nodes of a grown tree that stand for a component spelled out.

    A node whose text names one glyph and which has operands is a component the
    description named as a leaf and this build opened up; the root is the
    character itself, not a component crossed into.
    """
    found: set[int] = set()

    def walk(node: base.Node, top: bool) -> None:
        if node.leaf:
            return
        if not top and base.glyph_of(node.text, labels):
            found.add(id(node))
        for child in node.children:
            walk(child, False)

    walk(root, True)
    return found


def routes(node: base.Node, opened: set[int]) -> dict[int, list[tuple[str, int, str]]]:
    """Every node of a grown tree, by identity, with the way down to it.

    Each step is the operator walked, the operand taken, and the component that
    operator belongs to where the step crosses into one — '' where the operator
    is the character's own or one its description wrote out in full.
    """
    found: dict[int, list[tuple[str, int, str]]] = {id(node): []}

    def walk(here: base.Node, route: list[tuple[str, int, str]]) -> None:
        inside = here.text if id(here) in opened else ""
        for index, child in enumerate(here.children):
            step = route + [(here.operator or "", index, inside)]
            found[id(child)] = step
            walk(child, step)

    walk(node, [])
    return found


def selection(table: dict[str, list[str]], labels: dict[str, str]) -> list[tuple[str, str]]:
    """Every character whose decomposition reaches 山 at any depth."""
    return sorted((char, table[char][0]) for char in holders(table, labels))


def box_of(path: pathops.Path) -> list:
    return [round(value, 1) for value in path.bounds]


class Refused(base.Skipped):
    """Every 山 a character's cut found is the wrong shape.

    A verdict on the character, not a failed attempt at it: the pieces added up,
    the operands were laid out the way the operator reads, and the hand given to
    山 still does not look like 山. So this is not retried from another face or a
    shallower spelling out, which would only be a second roll of the dice for a
    character the measure has already answered.
    """

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


_masks: dict[str, object] = {}


def alone_masks(faces: list[base.Face]) -> list[tuple[str, object]]:
    """山 drawn alone, in each pinned face that draws it, as a normalised raster.

    Computed once per face and kept, since every instance of every character is
    held against the same few shapes.
    """
    found = []
    for face in faces:
        if face.name not in _masks:
            pieces = face.pieces(MOUNTAIN)
            _masks[face.name] = None if not pieces else mountain_shapes.raster(
                mountain_shapes.flatten(base.commands_of(base.union_of(pieces))),
                DISAGREEMENT_GRID)
        if _masks[face.name] is not None:
            found.append((face.name, _masks[face.name]))
    return found


SKELETON_GRID = 128
MAX_SKELETON_AWAY = 0.0499


def skeleton_points(shape: pathops.Path) -> "object":
    """The centre line of a shape, as the pixels the distance is taken over."""
    mask = mountain_shapes.raster(
        mountain_shapes.flatten(base.commands_of(shape)), SKELETON_GRID) > 0.5
    return mountain_thin.points(mountain_thin.skeleton(mask))


def skeleton_away(points, references: list[tuple[str, object]]) -> tuple[float, str]:
    """How far the cut's centre line runs from 山's, counting only the ink it adds.

    One-sided on purpose: a cut that swallows a neighbour grows a branch, and that is
    what this charges for. A cut that misses part of 山 is the filled gate's business.
    """
    return min((mountain_variants.chamfer_brute(points, line)["out"], name)
               for name, line in references)


def disagreement(ink: pathops.Path, masks: list[tuple[str, object]]) -> tuple[float, str]:
    """How far an instance's shape stands from 山 drawn alone, and in which face.

    1 − IoU between the two, each stretched on its own to fill the grid. The
    smallest reading over the faces is the one that counts, so a piece is faulted
    only when it looks unlike every 山 the pinned faces draw.
    """
    piece = mountain_shapes.raster(
        mountain_shapes.flatten(base.commands_of(ink)), DISAGREEMENT_GRID)
    return min((1 - mountain_shapes.iou(piece, mask), name) for name, mask in masks)


def instances(char: str, ids: str, root: base.Node, labels,
              faces: list[base.Face]) -> dict:
    """One character's 山 instances, or Skipped with the reason it could not be cut."""
    opened = opened_in(root, labels)
    where = routes(root, opened)
    face = faces[0]
    pieces = face.pieces(char)
    if not pieces:
        raise base.Skipped("the glyph draws no ink")
    drawn, divided = face.outline(char), base.union_of(pieces)
    if abs(abs(drawn.area) - abs(divided.area)) > 0.002 * max(abs(drawn.area), 1):
        raise base.Skipped("the pieces do not add up to the glyph the font draws")
    if len(pieces) < len(base.terminals(root)):
        raise base.Skipped(f"the glyph draws {base.count(len(pieces), 'piece')} for "
                           f"{base.count(len(base.terminals(root)), 'element')}")

    cutter = Enclosing(pieces, labels, faces)
    cut = cutter.cut(root, list(range(len(pieces))))

    # 山 alone, in the face that draws this character where it has it, so the
    # area ratio compares two drawings of one shape by one hand.
    reference = next((f for f in faces if f.pieces(MOUNTAIN)), None)
    if reference is None:
        raise base.Skipped("no pinned face draws 山 to measure against")
    alone = base.union_of(reference.pieces(MOUNTAIN))
    whole = abs(alone.area)
    # 山 alone in every face that draws it, to hold each instance's shape against.
    masks = alone_masks(faces)
    if not masks:
        raise base.Skipped("no pinned face draws 山 to compare shapes against")
    # The same references as centre lines, for the gate that reads added branches.
    skeletons = [(face.name, skeleton_points(base.union_of(face.pieces(MOUNTAIN))))
                 for face in faces if face.pieces(MOUNTAIN)]

    found, refused = [], []
    claimed: set[int] = set()
    for node, group in cut:
        if base.glyph_of(node.text, labels) != MOUNTAIN:
            continue
        route = where[id(node)]
        if not route:
            raise base.Skipped("the description is 山 itself")
        operator, index, _ = route[-1]
        # The components crossed into on the way down, outermost first: 岡 for
        # 剛, 崔 for 催, nothing for a 山 the character's own description names.
        through = [step[2] for step in route if step[2]]
        ink = base.union_of([pieces[i] for i in group])
        # Is the hand given to 山 shaped like a 山? Both are stretched to their
        # own box, so this asks about the figure and not the size it was drawn at.
        away, against = disagreement(ink, masks)
        down, downFace = skeleton_away(skeleton_points(ink), skeletons)
        if down >= MAX_SKELETON_AWAY:
            refused.append(
                f"the pieces given to {MOUNTAIN} at {position_of(operator, index)} carry "
                f"more centre line than {MOUNTAIN} has: thinned at {SKELETON_GRID}×"
                f"{SKELETON_GRID} the cut runs {down:.4f} from {MOUNTAIN} drawn alone in "
                f"{downFace}, one-sided, at or past the {MAX_SKELETON_AWAY} this build refuses")
            continue
        if away >= MAX_DISAGREEMENT:
            refused.append(
                f"the pieces given to {MOUNTAIN} at {position_of(operator, index)} are not "
                f"shaped like {MOUNTAIN}: stretched to its own box the group disagrees with "
                f"{MOUNTAIN} drawn alone in {against} over {away:.3f} of their ink "
                f"(1 − IoU on a {DISAGREEMENT_GRID}×{DISAGREEMENT_GRID} grid), at or past "
                f"the {MAX_DISAGREEMENT:.4f} this build refuses")
            continue
        claimed.update(group)
        # How much this instance looks like 山 drawn alone, normalised to its own
        # box, so a reader can rank the readings and look at the weakest first.
        fit = base.likeness(cutter.group_print(group), reference.whole(MOUNTAIN))
        if fit < MIN_FIT:  # only reached when a floor is asked for on the command line
            raise base.Skipped(
                f"the pieces given to {MOUNTAIN} at {position_of(operator, index)} "
                f"do not look like {MOUNTAIN} ({fit:.2f})")
        found.append({
            "fit": round(fit, 3),
            # 1 − IoU against 山 drawn alone, both stretched to their own box: the
            # measure the gate refuses on, kept on the survivors so a reader can
            # rank how close to the line each one came.
            "disagreement": round(away, 4),
            "disagreementAgainst": against,
            # The skeleton gate's reading, kept for the same reason.
            "skeletonAway": round(down, 4),
            "skeletonAgainst": downFace,
            "position": position_of(operator, index),
            "operator": operator,
            "operand": index + 1,
            # The operands walked to reach this 山, outermost first: the
            # instance's address inside the grown description. A step that
            # crosses into a component names it.
            "route": [{"operator": op, "operand": i + 1, "position": position_of(op, i),
                       **({"inside": inside} if inside else {})}
                      for op, i, inside in route],
            "depth": len(route),
            "through": through,
            # 1 where the character's own description names the 山, 2 where it
            # sits one component down, and so on. Depth-1 instances and deeper
            # ones are not the same kind of evidence.
            "level": len(through) + 1,
            "path": base.commands_of(ink),
            "box": box_of(ink),
            "area": round(abs(ink.area), 1),
            # Against 山 drawn alone in the same face: how much of a standing 山
            # this squashed one covers.
            "areaRatio": round(abs(ink.area) / whole, 4) if whole else None,
            "pieces": len(group),
        })
    if refused and not found:
        raise Refused(refused)
    if not found:
        raise base.Skipped("the decomposition reaches 山 but no leaf of the cut is 山")
    rest = [i for i in range(len(pieces)) if i not in claimed]
    return {
        "char": char,
        "ids": ids,
        # The tree the cut was actually made on: the description with the
        # components that hold a 山 spelled out, as far as the reading reached.
        "tree": spelled(root),
        "face": face.name,
        "referenceFace": reference.name,
        "likeness": round(min(cutter.marks), 3) if cutter.marks else None,
        "ownFace": all(face.whole(base.glyph_of(node.text, labels)) is not None
                       for node, _ in cut if base.glyph_of(node.text, labels)),
        # What the glyph draws outside its 山, for the faint figure behind it.
        # Ink the cut gave to a 山 that was then refused on shape is here, since
        # nothing in the record claims it as a 山 any more.
        "rest": [base.commands_of(pieces[i]) for i in rest],
        "instances": found,
        # Where some of this character's 山 were refused on shape and others
        # kept, the refusals, so the missing ones are accounted for and not
        # merely absent. A character whose every 山 was refused is in `skipped`.
        **({"refused": refused} if refused else {}),
    }


def build(faces: list[base.Face], only: str | None, limit: int | None, report) -> dict:
    table, labels = base.read_table(), base.read_labels()
    holds = holders(table, labels)
    chosen = selection(table, labels)
    if only:
        chosen = [(char, table[char][0]) for char in dict.fromkeys(only) if char in table]
    if limit:
        chosen = chosen[:limit]

    entries, skipped, shallower = [], [], []
    # How many instances the shape gate threw out, counting the ones inside
    # characters that left the dataset over it.
    refusals = 0
    for char, ids in chosen:
        drawn = [face for face in faces if face.draws(char)]
        if not drawn:
            skipped.append({"char": char, "ids": ids, "reason": "no pinned face draws it"})
            if report:
                report(char, entries, skipped)
            continue
        reasons: list[str] = []
        try:
            offered = readings(char, ids, table, labels, holds)
        except ValueError as reason:
            offered = []
            reasons.append(f"unreadable description: {reason}")
        entry, verdict = None, None
        # The fullest spelling out first, then shallower ones: a component the
        # font draws joined to its neighbour cannot be opened, and the 山 the
        # character names outright should not be lost with it.
        for cap, root in offered:
            for face in drawn:
                try:
                    entry = instances(char, ids, root, labels,
                                      [face, *(f for f in faces if f is not face)])
                except Refused as reason:
                    # The cut came off and its 山 are the wrong shape. That is an
                    # answer about the character, so the search stops here rather
                    # than looking for a face or a depth that lets it through.
                    verdict = f"{face.name}, {base.count(cap, 'component')} deep: {reason}"
                    refusals += len(reason.reasons)
                    break
                except base.Skipped as reason:
                    reasons.append(f"{face.name}, {base.count(cap, 'component')} deep: {reason}")
                    continue
                except (ValueError, KeyError, RecursionError) as reason:
                    reasons.append(f"{face.name}: unreadable description: {reason}")
                    continue
                entry["opened"] = cap
                entry["fullest"] = offered[0][0]
                if cap < offered[0][0]:
                    # The deeper reading did not hold; say so on the entry, so a
                    # reader knows this character's deeper 山 went unrecorded.
                    entry["closed"] = reasons[-1] if reasons else ""
                    shallower.append(char)
                break
            if entry is not None or verdict is not None:
                break
        if verdict is not None:
            skipped.append({"char": char, "ids": ids, "reason": verdict})
        elif entry is None:
            skipped.append({"char": char, "ids": ids,
                            "reason": reasons[-1] if reasons else "no reading reaches a 山"})
        elif entry is not None:
            refusals += len(entry.get("refused", ()))
            entries.append(entry)
        if report:
            report(char, entries, skipped)

    mountains = {}
    for face in faces:
        pieces = face.pieces(MOUNTAIN)
        if not pieces:
            continue
        ink = base.union_of(pieces)
        mountains[face.name] = {
            "path": base.commands_of(ink), "box": box_of(ink), "area": round(abs(ink.area), 1),
        }
    return {
        "format": "ids-input/mountain-instances",
        "version": 1,
        "element": MOUNTAIN,
        "faces": [{"name": face.name, "version": face.version,
                   "file": face.file, "sha256": face.pin["sha256"]} for face in faces],
        # 山 as each face draws it alone, the shape every instance is measured against.
        "alone": mountains,
        "attempted": len(chosen),
        "minFit": MIN_FIT,
        # The shape gate: an instance whose 1 − IoU against 山 drawn alone, both
        # stretched to their own box on this grid, reaches this number is not
        # written out, and the reading goes into the skip or onto the entry.
        "maxDisagreement": MAX_DISAGREEMENT,
        "disagreementGrid": DISAGREEMENT_GRID,
        "refused": refusals,
        # How many instances were found at each level of nesting: 1 where the
        # character's own description names the 山, 2 where it sits inside a
        # component, and so on.
        "levels": {str(level): sum(1 for entry in entries for instance in entry["instances"]
                                   if instance["level"] == level)
                   for level in sorted({instance["level"] for entry in entries
                                        for instance in entry["instances"]})},
        # Characters read at a shallower spelling out than they hold, because a
        # component the font draws joined to its neighbour could not be opened.
        # Each one says so on its entry, under `closed`.
        "shallower": shallower,
        "entries": entries,
        "skipped": skipped,
    }


def main() -> int:
    global MOUNTAIN, MAX_SKELETON_AWAY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, action="append", default=[],
                        help="a pinned face already on disk; repeat for several")
    parser.add_argument("--cache", type=Path, default=ROOT / "cache", help="where faces are kept")
    parser.add_argument("--refresh", action="store_true", help="fetch the faces again")
    parser.add_argument("--only", help="build just these characters")
    parser.add_argument("--limit", type=int, help="build only the first so many")
    parser.add_argument("--min-fit", type=float, default=MIN_FIT,
                        help="how much an instance must look like 山 alone")
    parser.add_argument("--max-skeleton-away", type=float, default=MAX_SKELETON_AWAY,
                        help="how far a cut's centre line may run from the component's own")
    parser.add_argument("--max-disagreement", type=float, default=MAX_DISAGREEMENT,
                        help="how far an instance's shape may stand from 山 drawn alone, "
                             "as 1 − IoU on normalised rasters")
    parser.add_argument("--component", default=MOUNTAIN,
                        help="the component to cut out, e.g. 山 or 口")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    MOUNTAIN = args.component
    MAX_SKELETON_AWAY = args.max_skeleton_away
    if args.out is None:
        args.out = TARGET if MOUNTAIN == "山" else TARGET.with_name(f"component-instances-{MOUNTAIN}.json.gz")

    globals()["MIN_FIT"] = args.min_fit
    globals()["MAX_DISAGREEMENT"] = args.max_disagreement
    faces = base.load_faces(args.font, args.cache, args.refresh, FACE_FILES)
    started = time.monotonic()

    def report(char, entries, skipped):
        if not args.quiet:
            done = len(entries) + len(skipped)
            print(f"\r{done} read, {len(entries)} cut, {len(skipped)} skipped, "
                  f"{time.monotonic() - started:.0f}s … {char}",
                  end="", file=sys.stderr, flush=True)

    document = build(faces, args.only, args.limit, report)
    if not args.quiet:
        print("\r" + " " * 72, end="\r", file=sys.stderr)

    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8", compresslevel=9) as out:
        out.write(raw)
    total = sum(len(entry["instances"]) for entry in document["entries"])
    shown = args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out
    print(f"{shown}: {len(document['entries'])} of "
          f"{document['attempted']} characters, {total} instances, "
          f"{args.out.stat().st_size:,} bytes gzipped from {len(raw):,}")
    print(f"{document['refused']} instances refused on shape at "
          f"1 − IoU ≥ {document['maxDisagreement']}")
    if document["skipped"]:
        print(f"\nskipped {len(document['skipped'])}:")
        grouped: dict[str, list[str]] = {}
        for row in document["skipped"]:
            grouped.setdefault(row["reason"], []).append(row["char"])
        for reason, chars in sorted(grouped.items(), key=lambda item: -len(item[1]))[:40]:
            print(f"  {len(chars):4d}  {reason}")
            print(f"        {''.join(chars)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
