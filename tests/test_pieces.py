import json
from pathlib import Path

import pathops

from han_decompose import geometry as G
from han_decompose import pieces
from han_decompose.pieces import Drawing
from han_decompose.schema import problems

from .conftest import FONT, GOLDEN
from .fonts import build, pinned_face, row


def polygon(*points: tuple[float, float]) -> G.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return path


def box(x0: float, y0: float, x1: float, y1: float, hole: bool = False) -> G.Path:
    corners = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
    return polygon(*(corners[::-1] if hole else corners))


def partition(paths: list[G.Path]) -> list[list[int]]:
    """The pieces of contours drawn together, as `Drawing` finds them."""
    whole = pathops.Path()
    for path in paths:
        path.draw(whole.getPen())
    whole.simplify()
    found = pieces.pieces_of(whole)
    members, joined = pieces.members_of(paths, found)
    return sorted(sorted(i for j in group for i in members[j]) for group in pieces._merged(found, joined))


def test_contours_that_overlap_are_one_piece_and_ones_apart_are_two() -> None:
    bar, stem, dot = box(0, 400, 600, 500), box(250, 0, 350, 800), box(700, 0, 800, 100)
    assert partition([bar, stem, dot]) == [[0, 1], [2]]


def test_a_counter_goes_with_the_piece_it_is_cut_out_of() -> None:
    frame, counter = box(0, 0, 900, 900), box(100, 100, 800, 800, hole=True)
    island, inner = box(300, 300, 600, 600), box(400, 400, 500, 500, hole=True)
    assert partition([frame, counter, island, inner]) == [[0, 1], [2, 3]]
    assert partition([island, inner, counter, frame]) == [[0, 1], [2, 3]]


def test_ink_too_small_to_be_a_piece_joins_the_nearest_one() -> None:
    assert partition([box(0, 0, 300, 300), box(600, 0, 900, 300), box(560, 100, 565, 105)]) == [[0], [1, 2]]


def test_one_contour_that_meets_itself_at_a_point_is_one_piece() -> None:
    hourglass = polygon((0, 0), (0, 300), (300, 300), (300, 600), (600, 600), (600, 300), (300, 300), (300, 0))
    whole = pathops.Path()
    hourglass.draw(whole.getPen())
    whole.simplify()
    assert len(pieces.pieces_of(whole)) == 2
    assert partition([hourglass]) == [[0]]
    assert partition([hourglass, box(700, 0, 900, 200)]) == [[0], [1]]


def test_the_pieces_of_a_glyph_are_read_from_the_font(tmp_path: Path) -> None:
    from han_decompose.outline import Face

    face = Face(row("test@1"), build(tmp_path / "test.ttf"))
    drawing = Drawing(face)
    pair = drawing.glyph("U+4E8C")
    assert pair is not None and pair.partition() == [[0], [1]] and pair.tiles
    assert [len(piece) for piece in pair.members] == [1, 1] and pair.contours_of([0, 1]) == [0, 1]
    assert pair.contours == face.contours("U+4E8C")
    assert drawing.glyph("U+4E8C") is pair
    assert drawing.glyph("U+5C71") is None
    space = drawing.glyph("U+0020")
    assert space is not None and space.pieces == [] and not space.tiles
    assert problems("outlines", outline_file("test@1", {"U+4E8C": pair.record()})) == []


def outline_file(font: str, glyphs: dict[str, object]) -> dict[str, object]:
    return {
        "format": "han-decompose/outlines@1.0",
        "font": font,
        "licence": "OFL-1.1",
        "copyright": "A font for tests.",
        "em": 1000,
        "q": 100,
        "glyphs": glyphs,
    }


def test_the_golden_outline_is_what_the_pinned_font_gives() -> None:
    golden = json.loads((GOLDEN / "outlines" / FONT / "050.json").read_text(encoding="utf-8"))
    drawing = Drawing(pinned_face(FONT))
    for selector, record in golden["glyphs"].items():
        glyph = drawing.glyph(selector)
        assert glyph is not None and glyph.record() == record and glyph.tiles


def test_an_island_inside_a_counter_is_a_piece_of_its_own() -> None:
    glyph = Drawing(pinned_face(FONT)).glyph("U+56DE")
    assert glyph is not None and glyph.partition() == [[0, 1], [2, 3]]
    scaled = Drawing(pinned_face("jigmo@20250912")).glyph("U+56DE")
    assert scaled is not None and scaled.partition() == [[0, 1], [2, 3]] and scaled.tiles


def test_components_plangothic_draws_as_one_contour_are_one_piece() -> None:
    # 𡹐 is ⿰山隹: one contour runs through the 山 and the 隹 and meets itself where they join.
    glyph = Drawing(pinned_face("plangothic-p1@2.9.5795")).glyph("U+21E50")
    assert glyph is not None and glyph.partition() == [[0, 1, 2, 3]] and glyph.tiles
