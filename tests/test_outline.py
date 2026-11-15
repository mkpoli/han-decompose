from pathlib import Path

import pytest

from han_decompose.outline import Chain, Face, commands
from han_decompose.schema import Json

from .fonts import build, pinned_face, row


@pytest.fixture
def face(tmp_path: Path) -> Face:
    return Face(row("test@1"), build(tmp_path / "test.ttf"))


def test_points_are_hundredths_on_a_1000_unit_em(face: Face) -> None:
    # 512 of 1024 units is 500 units: 50000 hundredths.
    assert face.contours("U+4E00") == [("MLLL", [0, 0, 0, 50000, 50000, 50000, 50000, 0])]
    assert face.advance("U+4E00") == 1000
    assert face.advance("U+0020") == 500


def test_a_curve_keeps_its_points_and_repeats_the_start_it_closes_on(face: Face) -> None:
    ((letters, points),) = face.contours("U+4E3F") or []
    assert letters == "MLQ3"
    # 100, 300, 301, 150, 250 of 1024: 9765.625, 29296.875, 29394.53125, 14648.4375, 24414.0625.
    assert points == [9766, 0, 29297, 0, 29395, 14648, 24414, 29395, 9766, 0]


def test_a_contour_without_an_on_curve_point_is_one_closed_run(face: Face) -> None:
    # 16 of 1024 units is 1562.5 hundredths: a tie, which goes to the even 1562.
    assert face.contours("U+3007") == [("Q4*", [0, 0, 0, 1562, 1562, 1562, 1562, 0])]


def test_a_composite_is_decomposed_in_the_order_of_its_components(face: Face) -> None:
    curve, square = face.contours("U+4E8C") or []
    assert curve[0] == "MLQ3" and curve[1][:2] == [9766, 58594]
    assert square == ("MLLL", [977, 0, 977, 50000, 50977, 50000, 50977, 0])


def test_a_glyph_without_ink_has_no_contour_and_an_unmapped_one_is_none(face: Face) -> None:
    assert face.contours("U+0020") == []
    assert face.contours("U+5C71") is None
    assert face.advance("U+5C71") is None


def test_a_variation_sequence_is_drawn_only_where_the_font_maps_it(face: Face) -> None:
    assert face.contours("U+4E00.E0100") == [("MLLL", [0, 0, 0, 25000, 50000, 25000, 50000, 0])]
    assert face.contours("U+4E00.E0101") == face.contours("U+4E00")
    assert face.contours("U+4E00.E0102") is None
    assert face.contours("U+4E3F.E0100") is None
    # A sequence that keeps the glyph of a base the font does not map draws nothing.
    assert face.contours("U+9FFF.FE00") is None


def test_a_glyph_is_reached_by_its_index(face: Face) -> None:
    assert face.glyph_name("gid.2") == "square"
    assert face.contours("gid.6") == face.contours("U+4E00.E0100")
    assert face.contours("gid.7") is None
    with pytest.raises(ValueError):
        face.contours("gid.02")


def test_selectors_list_what_the_font_maps(face: Face) -> None:
    assert list(face.selectors()) == ["U+0020", "U+3007", "U+4E00", "U+4E3F", "U+4E8C", "U+4E00.E0100", "U+4E00.E0101"]


def test_a_chain_takes_a_glyph_from_its_first_font_that_draws_it(tmp_path: Path) -> None:
    first = Face(row("first@1"), build(tmp_path / "first.ttf"))
    second = Face(row("second@1", 2048), build(tmp_path / "second.ttf", 2048, {0x5C71: "square"}))
    chain = Chain("test", [first, second])
    assert chain.face("U+4E00") is first
    assert chain.face("U+5C71") is second
    assert chain.face("U+50AC") is None
    assert second.contours("U+5C71") == [("MLLL", [0, 0, 0, 25000, 25000, 25000, 25000, 0])]
    assert list(chain.selectors()) == [*first.selectors(), "U+5C71"]


def test_a_variation_sequence_comes_from_the_first_font_that_maps_the_sequence(tmp_path: Path) -> None:
    first = Face(row("first@1"), build(tmp_path / "first.ttf"))
    later: dict[int, list[tuple[int, str | None]]] = {0xE0102: [(0x4E00, "square.alt")], 0xE0100: [(0x4E3F, "square")]}
    second = Face(row("second@1"), build(tmp_path / "second.ttf", sequences=later))
    with Chain("test", [first, second]) as chain:
        assert chain.face("U+4E00.E0100") is first
        assert chain.face("U+4E00.E0102") is second
        assert chain.face("U+4E3F.E0100") is second and chain.face("U+4E3F") is first
        assert list(chain.selectors())[-2:] == ["U+4E00.E0102", "U+4E3F.E0100"]


def test_a_variable_font_is_read_at_its_pinned_instance(tmp_path: Path) -> None:
    path = build(tmp_path / "variable.ttf", variable=True)
    # wght 400 is 3/8 of the way from 100 to 900: the upper edge rises 192 of 1024 units, to 687.5 units.
    face = Face({**row("variable@1"), "instance": {"wght": 400}}, path)
    assert face.contours("U+4E00") == [("MLLL", [0, 0, 0, 68750, 50000, 68750, 50000, 0])]
    assert Face({**row("variable@1"), "instance": {"wght": 100}}, path).contours("U+4E00") == [
        ("MLLL", [0, 0, 0, 50000, 50000, 50000, 50000, 0])
    ]
    assert face.contours("U+4E3F") == Face(row("static@1"), build(tmp_path / "static.ttf")).contours("U+4E3F")


@pytest.mark.parametrize(
    "instance, message",
    [({"wdth": 100}, "no axis wdth"), ({"wght": 5000}, "no axis wght that reaches 5000"), (None, "names no instance")],
)
def test_an_instance_the_font_does_not_have_is_refused(
    tmp_path: Path, instance: dict[str, float] | None, message: str
) -> None:
    pin = row("variable@1") if instance is None else {**row("variable@1"), "instance": instance}
    with pytest.raises(ValueError, match=message):
        Face(pin, build(tmp_path / "variable.ttf", variable=True))
    with pytest.raises(ValueError, match="no axis wght"):
        Face({**row("static@1"), "instance": {"wght": 400}}, build(tmp_path / "static.ttf"))


def test_a_face_index_goes_with_a_collection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="a face index exactly when its file is a collection"):
        Face({**row("test@1"), "index": 0}, build(tmp_path / "test.ttf"))


def test_a_closed_font_holds_no_file(tmp_path: Path) -> None:
    face = Face(row("test@1"), build(tmp_path / "test.ttf"))
    file = face.font.reader.file
    face.close()
    assert file.closed


def test_a_font_that_is_not_its_pin_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="1024 units per em, its pin says 1000"):
        Face(row("test@1", 1000), build(tmp_path / "test.ttf"))


def test_cubic_curves_are_kept() -> None:
    pen = [("moveTo", ((0, 0),)), ("curveTo", ((0, 1), (1, 2), (2, 2))), ("lineTo", ((2, 0),)), ("closePath", ())]
    assert commands(pen, 100) == [("MCL", [0, 0, 0, 100, 100, 200, 200, 200, 200, 0])]
    with pytest.raises(ValueError):
        commands([("addComponent", ("a", (1, 0, 0, 1, 0, 0)))], 100)


@pytest.mark.parametrize("selector", ["U+50AC", "U+5079"])
def test_the_golden_outlines_are_what_the_pinned_font_draws(outlines: Json, selector: str) -> None:
    drawn = pinned_face(outlines["font"]).contours(selector) or []
    assert [list(contour) for contour in drawn] == outlines["glyphs"][selector]["contours"]
    assert pinned_face(outlines["font"]).advance(selector) == outlines["glyphs"][selector]["advance"]
