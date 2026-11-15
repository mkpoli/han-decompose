"""Lift a component no code point names out of the characters written with it.

A CHISE entity (`&CDP-8958;`), a zi.tools stroke chain (`#(-𠃍㇉)`) or a numbered component of
BabelStone IDS (`{50}`) has no glyph in the fonts of a chain, but the characters described with it
do. Where such a character is the component beside encoded parts
only, the font draws them as pieces that do not touch, and the component is what is left once each
part's pieces are lifted away. A host whose part touches the component gives nothing.

In a host, the pieces given to a part are the group whose fingerprint best matches the part drawn
alone, on the side the operator puts it, by a margin over every other group. What is left stands
as the component when it is confirmed:

- by a reference glyph, where there is one, which then decides alone: the GlyphWiki glyph of an
  entity, the glyph BabelStone Han PUA draws for a numbered component;
- else by what another host leaves, two hosts agreeing;
- else, from one host, only when its parts lift away unmistakably.
"""

import gzip
import itertools
import json
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pathops
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

from .. import descriptions, pins
from .. import geometry as G
from .. import identifiers as I
from ..descriptions import Description, Table
from ..ids import Node, leaves, parse, spelled, walk, without_notes
from ..outline import Chain, Face
from ..pieces import Drawing, Glyph
from ..schema import Json
from . import reading
from .deal import GRID, Skipped

#: The raster the pieces are read on: one cell per this many units.
UNIT = 8
#: A group of pieces is the part when it matches the part drawn alone at least this well…
MATCH = 0.55
#: …and better than any other group by this much.
MARGIN = 0.04
#: A host is read only if it has at most this many pieces.
MOST_PIECES = 10
#: At most this many parts are lifted out of a host.
MOST_PARTS = 4
#: How many hosts are tried for each component: enough for a library of its places.
MOST_HOSTS = 40
#: What is left stands as the component when it matches the GlyphWiki glyph this well…
REFERENCE = 0.35
#: …or when another host leaves something this like it…
AGREE = 0.7
#: …or, from one host alone, when the parts lift away this clearly.
CLEAR_MATCH, CLEAR_MARGIN = 0.75, 0.2

BESIDE = {"⿰": "x", "⿱": "y", "⿲": "x", "⿳": "y"}
ENCLOSING = frozenset("⿴⿵⿶⿷⿸⿹⿺⿼⿽")
#: The operators whose operands make a component's library of places.
LEARNED = frozenset("⿰⿱⿸⿺⿵⿹⿶⿴⿷")
#: The source of the descriptions a kind of component is found in.
SOURCE_OF = {"entity": "chise", "chain": "zi-tools", "numbered": "babelstone"}
#: The font whose private use area draws the numbered components.
PUA = "babelstone-han-pua@1.472"
#: The source a subtraction is recorded in.
REGISTRY = "ids-input-components"

Mask = npt.NDArray[np.bool_]
_SELECTORS = "".join(chr(point) for point in range(0xFE00, 0xFE10))


def encoded(text: str) -> bool:
    """Whether a component is one character, with or without a variation selector after it."""
    return len(text.rstrip(_SELECTORS)) == 1


@dataclass
class Recipe:
    """A host a component can be cut from: the glyph to read, the parts to lift away, and, where
    the component is one of the operands of the description's root, the operator and its side."""

    host: str
    parts: list[str]
    op: str | None
    side: int
    siblings: list[str]
    #: The description the recipe was read from: the host's, or the component's subtraction.
    description: Description
    root: Node


def recipes(component: Json, table: Table) -> list[Recipe]:
    """The hosts of a component: first the subtraction the registry records (`㇯冐⺜`: 冐 without
    ⺜), then each character whose description holds the component once beside encoded parts only."""
    text = component["text"]
    found: list[Recipe] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def add(recipe: Recipe) -> None:
        key = (recipe.host, tuple(sorted(recipe.parts)))
        if key not in seen and 0 < len(recipe.parts) <= MOST_PARTS:
            seen.add(key)
            found.append(recipe)

    written = component.get("subtraction") or ""
    try:
        node: Node | None = parse(without_notes(written)) if written else None
    except ValueError:
        node = None
    if node is not None:
        root, removed = node, []
        while node.operator == "㇯" and encoded(node.children[1].text):
            removed.append(node.children[1].text)
            node = node.children[0]
        if node.leaf and encoded(node.text):
            add(Recipe(node.text, removed, "㇯", 0, removed, Description(REGISTRY, text, written), root))
    for host in component["usedIn"]:
        for description in table.of(host):
            if description.tags == "apparent":
                continue
            try:
                root = description.tree()
            except ValueError:
                continue
            others = [leaf.text for leaf in leaves(root)]
            if others.count(text) != 1:
                continue
            others.remove(text)
            if not all(encoded(leaf) for leaf in others):
                continue
            operands = [child.text for child in root.children]
            if text in operands:
                side = operands.index(text)
                siblings = [spelled(child) for index, child in enumerate(root.children) if index != side]
                add(Recipe(host, others, root.operator, side, siblings, description, root))
            else:
                add(Recipe(host, others, None, 0, others, description, root))
    return found[:MOST_HOSTS]


def mask(shape: G.Path) -> Mask:
    """A shape's ink on the raster of the em, rows from the top."""
    side = 1000 // UNIT + 1
    ys = 880 - (np.arange(side) + 0.5) * UNIT
    xs = (np.arange(side) + 0.5) * UNIT
    out = np.zeros((side, side), dtype=bool)
    for points in G.rings_of(shape):
        ring = np.asarray(points)
        x0, y0, x1, y1 = ring[:-1, 0], ring[:-1, 1], ring[1:, 0], ring[1:, 1]
        for row, y in enumerate(ys):
            cross = (y0 > y) != (y1 > y)
            if not cross.any():
                continue
            at = x0[cross] + (x1[cross] - x0[cross]) * (y - y0[cross]) / (y1[cross] - y0[cross])
            out[row] ^= (np.searchsorted(np.sort(at), xs) % 2).astype(bool)
    return out


def print_of(ink: Mask, grid: int = GRID) -> G.Array | None:
    """Coverage over a grid laid on the ink's own box: the shape, whatever its size."""
    rows, cols = np.nonzero(ink)
    if not len(rows):
        return None
    crop = ink[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1].astype(float)
    # A shape thinner than the grid is stretched first, so every grid row reads it whole.
    crop = np.repeat(np.repeat(crop, -(-grid // crop.shape[0]), axis=0), -(-grid // crop.shape[1]), axis=1)
    height, width = crop.shape
    ri = np.minimum((np.arange(height) * grid) // height, grid - 1)
    ci = np.minimum((np.arange(width) * grid) // width, grid - 1)
    total = np.zeros((grid, grid))
    count = np.zeros((grid, grid))
    np.add.at(total, (ri[:, None], ci[None, :]), crop)
    np.add.at(count, (ri[:, None], ci[None, :]), 1)
    out: G.Array = total / np.maximum(count, 1)
    return out


def like(first: G.Array | None, second: G.Array | None) -> float:
    """Agreement between two prints, 1 for the same ink everywhere, 0 where one is missing."""
    if first is None or second is None:
        return 0.0
    total = np.maximum(first, second).sum()
    return float(np.minimum(first, second).sum() / total) if total else 0.0


def _centre(ink: Mask) -> tuple[float, float]:
    rows, cols = np.nonzero(ink)
    return float(cols.mean()), float(rows.mean())


def _box(ink: Mask) -> tuple[int, int, int, int]:
    rows, cols = np.nonzero(ink)
    return int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max())


def placed(recipe: Recipe, part: Mask, rest: Mask) -> bool:
    """Whether a part's pieces sit where the operator puts it, when the component is one of the
    operator's two operands and the part the other."""
    if len(recipe.parts) != 1 or recipe.op is None:
        return True
    if recipe.op in BESIDE:
        axis = 0 if BESIDE[recipe.op] == "x" else 1
        here, there = _centre(part)[axis], _centre(rest)[axis]
        return there < here if recipe.side == 0 else here < there
    if recipe.op in ENCLOSING:
        inner, outer = (part, rest) if recipe.side == 0 else (rest, part)
        ix0, iy0, ix1, iy1 = _box(inner)
        ox0, oy0, ox1, oy1 = _box(outer)
        slack = 3
        return ix0 >= ox0 - slack and iy0 >= oy0 - slack and ix1 <= ox1 + slack and iy1 <= oy1 + slack
    return True


def _selector(char: str) -> str:
    return f"U+{ord(char[0]):04X}"


def drawn(drawings: Sequence[Drawing], char: str, first: Drawing | None = None) -> tuple[Drawing, Glyph] | None:
    """A character's glyph from `first` if it draws it with ink, else from the first font of the
    chain that does."""
    for drawing in [*([first] if first else []), *drawings]:
        glyph = drawing.glyph(_selector(char))
        if glyph is not None and glyph.pieces:
            return drawing, glyph
    return None


def _masks(drawing: Drawing, glyph: Glyph) -> list[Mask]:
    key = ("lift", glyph.selector)
    if key not in drawing.kept:
        drawing.kept[key] = [mask(piece) for piece in glyph.pieces]
    found: list[Mask] = drawing.kept[key]
    return found


def _ink(masks: Sequence[Mask], indices: Any) -> Mask:
    out: Mask = np.logical_or.reduce([masks[index] for index in indices])
    return out


@dataclass
class Lift:
    """What a host leaves once each part's pieces are lifted away."""

    recipe: Recipe
    drawing: Drawing
    glyph: Glyph
    #: The pieces left, and the pieces each part took, in the order the parts were lifted.
    kept: list[int]
    taken: list[tuple[str, list[int], float]]
    match: float
    margin: float
    print: G.Array | None
    #: How many other hosts leave the same shape, the likeness to the reference glyph, and
    #: whether the cut stands as the component.
    agree: int = 0
    reference: float | None = None
    stands: bool = False
    extra: Json = field(default_factory=dict)

    @property
    def single(self) -> bool:
        return self.match >= CLEAR_MATCH and self.margin >= CLEAR_MARGIN


def lift(drawings: Sequence[Drawing], recipe: Recipe) -> Lift:
    """One host read by a recipe, or Skipped with the reason nothing was lifted."""
    host = drawn(drawings, recipe.host)
    if host is None:
        raise Skipped("no-face", "no font of the chain draws the host with ink")
    drawing, glyph = host
    if len(glyph.pieces) < 2:
        raise Skipped("too-few-pieces", "the host is one piece")
    if len(glyph.pieces) > MOST_PIECES:
        raise Skipped("too-many-pieces", f"the host has {len(glyph.pieces)} pieces, more than {MOST_PIECES}")
    if not glyph.tiles:
        raise Skipped("does-not-tile", "the pieces do not add up to the glyph the font draws")
    alone = {part: drawn(drawings, part, drawing) for part in recipe.parts}
    missing = [part for part, found in alone.items() if found is None]
    if missing:
        raise Skipped("no-reference-glyph", f"no font of the chain draws {', '.join(missing)}")
    masks = _masks(drawing, glyph)
    references = {part: _ink(_masks(*found), range(len(found[1].pieces))) for part, found in alone.items() if found}
    left = set(range(len(glyph.pieces)))
    taken: list[tuple[str, list[int], float]] = []
    margins = []
    for part in sorted(recipe.parts, key=lambda part: -references[part].sum()):
        reference = print_of(references[part])
        scored = []
        for size in range(1, len(left)):
            for chosen in itertools.combinations(sorted(left), size):
                ink, rest = _ink(masks, chosen), _ink(masks, left - set(chosen))
                if ink.any() and rest.any():
                    scored.append((like(print_of(ink), reference), chosen, placed(recipe, ink, rest)))
        fits = [row for row in scored if row[2]]
        if not fits:
            raise Skipped(
                "layout-mismatch", f"no group of pieces sits where {recipe.op or 'the description'} puts {part}"
            )
        best, chosen, _ = max(fits, key=lambda row: row[0])
        # The margin is over every other group, wherever it sits: a host where position leaves one
        # candidate has not shown that the part stands out.
        second = max((row[0] for row in scored if row[1] != chosen), default=0.0)
        if best < MATCH:
            raise Skipped("unlike-element", f"no group of pieces looks like {part} ({best:.2f})")
        if best - second < MARGIN:
            raise Skipped("ambiguous", f"two groups of pieces look like {part} equally well")
        left -= set(chosen)
        taken.append((part, list(chosen), best))
        margins.append(best - second)
    return Lift(
        recipe,
        drawing,
        glyph,
        sorted(left),
        taken,
        round(min(score for _, _, score in taken), 3),
        round(min(margins), 3),
        print_of(_ink(masks, left)),
    )


def settle(lifts: Sequence[Lift], reference: G.Array | None) -> tuple[Lift | None, dict[str, list[Lift]]]:
    """Which of a component's lifts stands as its form, and its library: every host whose cut
    confirms the form, by the place the operator gives the component, best match first."""
    best: tuple[float, Lift] | None = None
    for got in lifts:
        got.agree = len({
            other.recipe.host
            for other in lifts
            if other.recipe.host != got.recipe.host and like(got.print, other.print) >= AGREE
        })  # fmt: skip
        got.reference = like(got.print, reference) if reference is not None else None
        # A glyph to hold the cut against decides: hosts agreeing on a cut it rejects agree on a
        # misreading.
        got.stands = got.reference >= REFERENCE if got.reference is not None else got.agree >= 1 or got.single
        score = (got.reference or 0) + got.agree + got.match
        if got.stands and (best is None or score > best[0]):
            best = (score, got)
    if best is None:
        return None, {}
    form = best[1]
    library: dict[str, list[Lift]] = {}
    for other in sorted(lifts, key=lambda row: -row.match):
        op = other.recipe.op
        if op not in LEARNED or (other is not form and like(other.print, form.print) < AGREE):
            continue
        place = reading.place(op, other.recipe.side)
        if any(row.recipe.host == other.recipe.host for row in library.get(place, [])):
            continue
        library.setdefault(place, []).append(other)
    return form, library


def basis(form: Lift) -> str:
    """What a form rests on: the reference glyph, hosts agreeing, or one clear host."""
    return "reference" if form.reference is not None else "agree" if form.agree else "single"


def record(got: Lift, text: str, reference_glyph: str | None = None) -> Json:
    """A lift as a reading of its host glyph: the component's cut, and each part's where the
    parts can be told apart."""
    recipe, glyph = got.recipe, got.glyph
    root, description = recipe.root, recipe.description
    evidence: Json = {"match": got.match, "margin": got.margin, "agree": got.agree}
    checks: Json
    if got.reference is not None:
        evidence["reference"] = reading.number(got.reference, 4)
        if reference_glyph:
            evidence["referenceGlyph"] = reference_glyph
        checks = {"reference": {"value": evidence["reference"], "limit": REFERENCE, "pass": got.stands}}
    elif got.agree or not got.single:
        checks = {"agree": {"value": got.agree, "limit": 1, "pass": got.stands}}
    else:
        checks = {"single": {"value": got.match, "limit": CLEAR_MATCH, "pass": got.stands}}
    more: Json = {"evidence": evidence, "checks": checks, "calibrated": False}
    status = "accepted" if got.stands else "refused"
    kept = glyph.contours_of(got.kept)
    if recipe.op == "㇯":
        # The description is the component's own: the host without its parts. Its root is the
        # component, and the parts are no part of it.
        cuts = [reading.cut(glyph, description, root, (), root, kept, status, **more)]
        return reading.reading(glyph, description, root, "lift", "piece", cuts, {"match": got.match})
    paths = {node.text: path for path, node in walk(root) if node.leaf}
    nodes = {path: node for path, node in walk(root)}
    held = {paths[text]: kept}
    if len(set(recipe.parts)) == len(recipe.parts):
        held.update({paths[part]: glyph.contours_of(group) for part, group, _ in got.taken})
    cuts = []
    for path, indices in held.items():
        extra: Json = dict(more) if nodes[path].text == text else {}
        if nodes[path].text != text:
            extra["evidence"] = {"match": reading.number(next(s for p, _, s in got.taken if p == nodes[path].text), 4)}
        if len(held) > 1:
            under = [other for at, other in held.items() if at[: len(path) - 1] == path[:-1]]
            extra["frame"] = reading.frame(glyph, under)
        own = status if nodes[path].text == text else "accepted"
        cuts.append(reading.cut(glyph, description, root, path, nodes[path], indices, own, **extra))
    return reading.reading(glyph, description, root, "lift", "piece", cuts, {"match": got.match, "margin": got.margin})


def skipped(recipe: Recipe, drawings: Sequence[Drawing], reason: Skipped) -> tuple[Json, str]:
    """A recipe that lifted nothing, as a skipped attempt, and the font whose files hold it."""
    host = next((d for d in drawings if d.glyph(_selector(recipe.host)) is not None), None)
    glyph = host.glyph(_selector(recipe.host)) if host else None
    glyph_id = I.glyph_id(host.id, _selector(recipe.host)) if host and glyph and glyph.contours else None
    return (
        reading.skipped(recipe.description, reason.code, reason.text, glyph_id),
        host.id if host else drawings[0].id,
    )


def glyphwiki(outlines: Json) -> dict[str, tuple[str, G.Array | None]]:
    """Each component's GlyphWiki glyph, by the component's text: its name and its print."""
    out = {}
    for text, name in outlines["names"].items():
        d = outlines["outlines"].get(name)
        if not d:
            continue
        path = pathops.Path()
        parse_path(d, path.getPen())
        # GlyphWiki draws on a 200-unit square, y down: turn it onto the em the cuts are read on.
        flipped = pathops.Path()
        path.draw(TransformPen(flipped.getPen(), (5, 0, 0, -5, 0, 880)))
        flipped.simplify()
        out[text] = (name, print_of(mask(flipped)))
    return out


@dataclass
class Outcome:
    """What lifting made of one component in one chain."""

    component: str
    kind: str
    #: Every host read, as a reading, and every host that gave nothing.
    readings: list[Json] = field(default_factory=list)
    skipped: list[tuple[Json, str]] = field(default_factory=list)
    #: The cut that stands as the component's form, with what it rests on; None where none stands.
    form: Json | None = None
    #: The cuts that confirm the form, by place.
    library: dict[str, list[str]] = field(default_factory=dict)
    #: The outline records of the glyphs named, by glyph identifier.
    glyphs: dict[str, Json] = field(default_factory=dict)


def _cut_of(row: Json, text: str) -> Json:
    """The component's own cut in a reading made by `record`."""
    return next(cut for cut in row["cuts"] if cut["text"] == text or not cut["path"])


def component(
    row: Json, tables: dict[str, Table], drawings: Sequence[Drawing], references: dict[str, tuple[str, G.Array | None]]
) -> Outcome:
    """Every host of one component read in one chain, the form that stands and its library."""
    text = row["text"]
    out = Outcome(I.component_of(text), row["kind"])
    lifts = []
    for recipe in recipes(row, tables[SOURCE_OF[row["kind"]]]):
        try:
            lifts.append(lift(drawings, recipe))
        except Skipped as reason:
            out.skipped.append(skipped(recipe, drawings, reason))
            host = drawn(drawings, recipe.host)
            if host is not None and "glyph" in out.skipped[-1][0]:
                out.glyphs.setdefault(out.skipped[-1][0]["glyph"], host[1].record())
    name, reference = references.get(text, (None, None))
    form, library = settle(lifts, reference)
    rows = {id(got): record(got, text, name) for got in lifts}
    for got in lifts:
        out.readings.append(rows[id(got)])
        out.glyphs.setdefault(rows[id(got)]["glyph"], got.glyph.record())
    if form is not None:
        cut = _cut_of(rows[id(form)], text)
        out.form = {"cut": cut["id"], "sig": cut["sig"], "basis": basis(form), "hosts": len(lifts)}
        out.library = {
            place: [_cut_of(rows[id(got)], text)["id"] for got in members] for place, members in sorted(library.items())
        }
    return out


def numbered(table: Table, pua: Drawing) -> dict[str, tuple[str, G.Array | None]]:
    """Each numbered component's glyph in BabelStone Han PUA, by the component's text: the glyph's
    identifier and its print."""
    out = {}
    for name, row in table.numbered.items():
        glyph = pua.glyph(f"U+{ord(row.pua):04X}") if row.pua else None
        if glyph is not None and glyph.pieces:
            out[name] = (I.glyph_id(pua.id, glyph.selector), print_of(mask(glyph.outline)))
    return out


def registry(cache: Path | None = None) -> list[Json]:
    """The components to lift: the entities, chains and numbered components of the pinned
    ids-input registry."""
    paths = pins.source_paths(pins.source(REGISTRY), cache, fetch=False)
    rows: list[Json] = json.loads(gzip.decompress(paths["custom-components.json.gz"].read_bytes()))["components"]
    return [row for row in rows if row["kind"] in SOURCE_OF]


_STATE: dict[str, Any] = {}


def _open(chain: str, cache: Path | None) -> None:
    _STATE["drawings"] = [Drawing(face) for face in Chain.pinned(chain, cache).faces]
    _STATE["tables"] = {source: descriptions.table(source, cache) for source in set(SOURCE_OF.values())}
    paths = pins.source_paths(pins.source("glyphwiki"), cache, fetch=False)
    _STATE["references"] = glyphwiki(json.loads(gzip.decompress(paths["custom-outlines.json.gz"].read_bytes())))
    _STATE["references"] |= numbered(_STATE["tables"]["babelstone"], Drawing(Face.pinned(PUA, cache)))


def _work(rows: list[Json]) -> list[Outcome]:
    return [component(row, _STATE["tables"], _STATE["drawings"], _STATE["references"]) for row in rows]


def run(chain: str = "sans", workers: int = 4, cache: Path | None = None) -> Iterator[Outcome]:
    """Every entity, chain and numbered component of the registry lifted in one chain, on several
    processes, in the registry's order whatever their number."""
    rows = registry(cache)
    jobs = [rows[at : at + 20] for at in range(0, len(rows), 20)]
    with ProcessPoolExecutor(workers, initializer=_open, initargs=(chain, cache)) as pool:
        for outcomes in pool.map(_work, jobs):
            yield from outcomes
