"""A glyph's pieces: the sets of contours whose ink touches or overlaps, with the counters inside.

The font draws a stroke as a contour and lets contours overlap. Merging the overlaps leaves
outlines that are apart or nested, and each outer boundary with the counters cut out of it is one
piece. A cutter hands whole pieces to the components of a description; a piece is then written as
the indices of the font's own contours that lie in it.
"""

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pathops
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen

from . import geometry as G
from .outline import EM, Contour, Face, commands
from .schema import Json, box


def pieces_of(path: G.Path) -> list[G.Path]:
    """The untouching pieces of a merged outline, counters kept open, in `geometry.piece_order`.

    A merged outline nests: an outer boundary, the counters cut out of it, and (in 回) a further
    island drawn inside a counter, which is a piece of its own. So contours are read by how deep
    they sit: one that an even number of others enclose is a piece's boundary, and what it gives
    up is the contours immediately inside it.
    """
    contours = [contour for contour in path.contours if abs(contour.area) >= G.EPS_AREA]
    shapes = [G.filled(contour) for contour in contours]
    depth = [
        sum(1 for j, other in enumerate(shapes) if j != i and G.inside(shape, other)) for i, shape in enumerate(shapes)
    ]
    found = []
    for i, shape in enumerate(shapes):
        if depth[i] % 2:
            continue
        counters = [other for j, other in enumerate(shapes) if depth[j] == depth[i] + 1 and G.inside(other, shape)]
        piece = shape
        if counters:
            piece = pathops.op(shape, G.union_of(counters), pathops.PathOp.DIFFERENCE)
            piece.simplify()
        if abs(piece.area) >= G.EPS_AREA:
            found.append(piece)
    return sorted(found, key=G.piece_order)


def _overlap(first: G.Box, second: G.Box) -> bool:
    return first[0] <= second[2] and second[0] <= first[2] and first[1] <= second[3] and second[1] <= first[3]


def _shared(first: G.Path, second: G.Path) -> float:
    """The area two shapes have in common."""
    if not _overlap(first.bounds, second.bounds):
        return 0.0
    return float(abs(pathops.op(first, second, pathops.PathOp.INTERSECTION).area))


def members_of(paths: Sequence[G.Path], pieces: Sequence[G.Path]) -> tuple[list[list[int]], list[set[int]]]:
    """The contours of each piece, as indices into `paths`, ascending, and the sets of pieces that
    one contour runs through.

    A contour belongs to the smallest piece whose outer boundary encloses it: ink lies within the
    boundary of the piece it is part of, and a counter within the boundary of the piece it is cut
    out of. A contour no single boundary encloses goes to the piece it shares most ink with. Where
    it shares ink with several, the font draws them as one contour that only meets itself at a
    point, and no set of whole contours tells them apart: they are named together. A contour
    without ink in any piece goes with the contour it cuts into, or to the nearest piece.
    """
    outers = [
        max((G.filled(contour) for contour in piece.contours), key=lambda shape: abs(shape.area)) for piece in pieces
    ]
    order = sorted(range(len(pieces)), key=lambda j: abs(outers[j].area))
    out: list[list[int]] = [[] for _ in pieces]
    joined: list[set[int]] = []
    homes: list[int | None] = []
    for path in paths:
        home = None
        if abs(path.area) > 1e-6:
            home = next(
                (j for j in order if _overlap(path.bounds, outers[j].bounds) and G.inside(path, outers[j])), None
            )
            if home is None:
                shared = [_shared(path, piece) for piece in pieces]
                if shared and max(shared) > 0:
                    home = shared.index(max(shared))
                    through = {j for j, area in enumerate(shared) if area >= G.EPS_AREA}
                    if len(through) > 1:
                        joined.append(through)
        homes.append(home)
    # A contour without ink in any piece cuts into another contour (a notch in a piece's edge):
    # it goes with the contour it shares most area with, and failing that to the nearest piece.
    for index, path in enumerate(paths):
        if homes[index] is not None:
            continue
        shared = [_shared(path, other) if homes[k] is not None else 0.0 for k, other in enumerate(paths)]
        if shared and max(shared) > 0:
            homes[index] = homes[shared.index(max(shared))]
            continue
        x, y = (path.bounds[0] + path.bounds[2]) / 2, (path.bounds[1] + path.bounds[3]) / 2

        def away(j: int, x: float = x, y: float = y) -> float:
            x0, y0, x1, y1 = pieces[j].bounds
            return float(max(x0 - x, 0, x - x1) ** 2 + max(y0 - y, 0, y - y1) ** 2)

        homes[index] = min(range(len(pieces)), key=away)
    for index, home in enumerate(homes):
        assert home is not None
        out[home].append(index)
    # A piece left without a contour is drawn by a contour that has its home elsewhere.
    for j, piece in enumerate(pieces):
        if out[j]:
            continue
        shared = [_shared(path, piece) for path in paths]
        if shared and max(shared) > 0:
            drawer = shared.index(max(shared))
            joined.append({j, next(k for k, indices in enumerate(out) if drawer in indices)})
    return out, joined


def _together(pieces: Sequence[G.Path]) -> G.Path:
    """Pieces that meet at a point as one shape: their contours side by side, none merged."""
    out = pathops.Path()
    pen = out.getPen()
    for piece in pieces:
        piece.draw(pen)
    return out


def _merged(pieces: Sequence[G.Path], joined: Sequence[set[int]]) -> list[list[int]]:
    """The pieces grouped so that every set in `joined` falls in one group."""
    group = list(range(len(pieces)))

    def find(j: int) -> int:
        while group[j] != j:
            group[j] = group[group[j]]
            j = group[j]
        return j

    for through in joined:
        first, *rest = sorted(through)
        for other in rest:
            group[find(other)] = find(first)
    found: dict[int, list[int]] = {}
    for j in range(len(pieces)):
        found.setdefault(find(j), []).append(j)
    return list(found.values())


@dataclass
class Glyph:
    """One glyph as a cutter reads it."""

    font: str
    selector: str
    #: The contours as the format writes them, in the font's order.
    contours: list[Contour]
    #: The same contours as shapes on the 1000-unit em, each alone.
    paths: list[G.Path]
    #: The whole glyph with its overlaps merged.
    outline: G.Path
    #: The pieces of the merged outline: untouching, or met only at a point by different contours.
    pieces: list[G.Path]
    #: The contour indices of each piece; empty for a piece no contour lies in.
    members: list[list[int]]
    advance: float
    #: GlyphWiki glyphs only: each stroke's type and the contours it drew.
    strokes: list[Json] | None = None
    _edges: dict[int, G.Array] = field(default_factory=dict, repr=False)
    _tiles: bool | None = field(default=None, repr=False)

    @property
    def tiles(self) -> bool:
        """Whether the pieces are the glyph and their contours draw them: the pieces together
        cover the ink the font draws, every piece has contours of its own, and those contours
        drawn alone give the piece's ink."""
        if self._tiles is None:
            self._tiles = self._check()
        return self._tiles

    def _check(self) -> bool:
        if not self.pieces or not all(self.members):
            return False
        drawn, divided = abs(self.outline.area), sum(abs(piece.area) for piece in self.pieces)
        if abs(drawn - divided) > 0.002 * max(drawn, 1):
            return False
        for piece, indices in zip(self.pieces, self.members, strict=True):
            alone = pathops.Path()
            for index in indices:
                self.paths[index].draw(alone.getPen())
            alone.simplify()
            if abs(abs(alone.area) - abs(piece.area)) > max(0.01 * abs(piece.area), G.EPS_AREA):
                return False
        return True

    def edges(self, piece: int) -> G.Array:
        """A piece flattened to edges, kept once made."""
        if piece not in self._edges:
            self._edges[piece] = G.edges_of(self.pieces[piece])
        return self._edges[piece]

    def contours_of(self, group: Sequence[int]) -> list[int]:
        """The contour indices of a group of pieces, ascending."""
        return sorted(index for piece in group for index in self.members[piece])

    def partition(self) -> list[list[int]]:
        """The pieces as the outline file writes them: each ascending, ordered by first index."""
        if not self.pieces:
            # Ink too small to be a piece is still the glyph's one piece in the file.
            return [list(range(len(self.contours)))] if self.contours else []
        return sorted((piece for piece in self.members if piece), key=lambda piece: piece[0])

    def record(self) -> Json:
        """The glyph as an outline file holds it (`docs/format.md`, 4.3)."""
        if not self.contours:
            raise ValueError(f"{self.font}/{self.selector} draws no ink.")
        advance = int(self.advance) if self.advance == int(self.advance) else self.advance
        out: Json = {
            "contours": [[letters, points] for letters, points in self.contours],
            "pieces": self.partition(),
            "box": box(self.contours, range(len(self.contours))),
            "advance": advance,
        }
        if self.strokes is not None:
            out["strokes"] = self.strokes
        return out


def assemble(
    font: str, selector: str, contours: list[Contour], paths: list[G.Path], outline: G.Path, advance: float
) -> Glyph:
    """A glyph from its contours, each as a shape on its own, and the shape of all of them: the
    outline is merged and divided into pieces, and each contour is given to one."""
    members: list[list[int]] = []
    try:
        outline.simplify()
        pieces = pieces_of(outline)
    except pathops.PathOpsError:
        pieces = []
    if pieces:
        members, joined = members_of(paths, pieces)
        if joined:
            # Pieces one contour runs through are one piece: whole contours cannot part them.
            groups = _merged(pieces, joined)
            both = sorted(
                (
                    (_together([pieces[j] for j in group]) if len(group) > 1 else pieces[group[0]], group)
                    for group in groups
                ),
                key=lambda pair: G.piece_order(pair[0]),
            )
            pieces = [piece for piece, _ in both]
            members = [sorted(index for j in group for index in members[j]) for _, group in both]
    return Glyph(
        font=font,
        selector=selector,
        contours=contours,
        paths=paths,
        outline=outline,
        pieces=pieces,
        members=members,
        advance=advance,
    )


class Drawing:
    """One font's glyphs as shapes and pieces, each read once."""

    #: How many glyphs are held at once; the least recently asked for goes first.
    HELD = 2048

    def __init__(self, face: Face):
        self.face = face
        self.id = face.id
        self._glyphs: OrderedDict[str, Glyph | None] = OrderedDict()
        #: What a cutter or a gate keeps per font, by a key of its own.
        self.kept: dict[Any, Any] = {}

    def glyph(self, selector: str) -> Glyph | None:
        """The glyph a selector reaches, or None when the font does not map it. A glyph whose
        outlines pathops cannot merge is read without pieces."""
        if selector in self._glyphs:
            self._glyphs.move_to_end(selector)
            return self._glyphs[selector]
        self._glyphs[selector] = self._read(selector)
        if len(self._glyphs) > self.HELD:
            self._glyphs.popitem(last=False)
        return self._glyphs[selector]

    def _read(self, selector: str) -> Glyph | None:
        face = self.face
        name = face.glyph_name(selector)
        if name is None:
            return None
        pen = DecomposingRecordingPen(face._glyphs)
        face._glyphs[name].draw(pen)
        scale = EM / face.upem
        transform = (scale, 0, 0, scale, 0, 0)

        def draw(calls: Sequence[tuple[str, tuple[Any, ...]]]) -> G.Path:
            path = pathops.Path()
            target = path.getPen()
            target = TransformPen(target, transform) if scale != 1 else target
            for verb, arguments in calls:
                getattr(target, verb)(*arguments)
            return path

        paths, current = [], []
        for call in pen.value:
            current.append(call)
            if call[0] in ("closePath", "endPath"):
                paths.append(draw(current))
                current = []
        return assemble(
            face.id,
            selector,
            commands(pen.value, face._scale),
            paths,
            draw(pen.value),
            round(face._glyphs[name].width * EM / face.upem, 2),
        )
