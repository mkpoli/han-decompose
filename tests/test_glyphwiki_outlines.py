import gzip
import json
from pathlib import Path

import pytest

from han_decompose import glyphwiki as gw
from han_decompose import glyphwiki_outlines as O
from han_decompose import outlines, pins
from han_decompose.schema import validate
from han_decompose.store import outline_head

DUMP = Path(__file__).parent / "fixtures" / "glyphwiki" / "dump.txt"
FONT = "glyphwiki@20261115"


@pytest.fixture(scope="module")
def dump() -> gw.Dump:
    return gw.Dump(DUMP, gw.DUMP_URL, 114464920, "ecf2cd5b" * 8, "2026-11-15T17:01:31Z")


def test_the_font_row_follows_the_registry_schema(dump: gw.Dump) -> None:
    row = O.font_row(dump)
    assert row["id"] == FONT and row["upem"] == 200 and row["grain"] == "contour"
    assert row["renderer"]["commit"] == "49232bac0348fe815f4200d4116ab7917e0db47f"
    validate("fonts", {**pins.fonts(), "fonts": [*pins.fonts()["fonts"], row]})


@pytest.mark.parametrize(
    ("name", "selector"),
    [
        ("u793e", "U+793E"),
        ("u845b-ue0100", "U+845B.E0100"),
        ("u793e-j", "name.u793e-j"),
        ("u845b-ue0101-var-001", "name.u845b-ue0101-var-001"),
        ("u793b-01", "name.u793b-01"),
        ("cdp-8bf9", None),
    ],
)
def test_names_are_filed_under_their_selector(name: str, selector: str | None) -> None:
    assert O.selector_of(name) == selector


def drawn(*names: str) -> dict[str, gw.Drawing]:
    out = {}
    for row in gw.draw(names, DUMP):
        assert isinstance(row, gw.Drawing)
        selector = O.selector_of(row.name)
        assert selector is not None
        out[selector] = row
    return out


def test_a_glyph_keeps_its_strokes_and_its_polygons_run_one_way() -> None:
    ((selector, drawing),) = drawn("u793e").items()
    glyph = O.glyph_of(FONT, selector, drawing)
    record = glyph.record()
    assert [s["contours"] for s in record["strokes"]][:2] == [[0, 1], [2]]
    assert [s["type"] for s in record["strokes"]] == [1, 1, 2, 1, 2, 1, 1, 1]
    assert len(record["contours"]) == len(drawing.contours)
    assert record["pieces"] == [list(range(8)), list(range(8, 14))]
    assert record["advance"] == 1000
    # KAGE's frame is 200 units, y down: ink at 9.3 across and 12 down is 46.5 and 940 up the em.
    assert record["box"][0] == 46.5 and record["box"][3] == 940
    for letters, points in record["contours"]:
        area = sum(
            points[i] * points[(i + 3) % len(points)] - points[(i + 2) % len(points)] * points[i + 1]
            for i in range(0, len(points), 2)
        )
        assert letters.startswith("M") and set(letters[1:]) <= {"L"} and area <= 0


def test_the_existing_writer_writes_the_block_of_a_valid_outline_file(tmp_path: Path, dump: gw.Dump) -> None:
    row = O.font_row(dump)
    held = drawn("u793e", "u793a-01", "u845b-ue0100")
    block = outlines.write_block(O.Drawn(FONT, held), "079", ["U+793E"], tmp_path, row)
    assert (block.written, block.empty, block.failed) == (1, 0, [])
    file = json.loads(gzip.decompress((tmp_path / "outlines" / FONT / "079.json.gz").read_bytes()))
    validate("outlines", file)
    assert file["licence"] == "LicenseRef-GlyphWiki" and list(file["glyphs"]) == ["U+793E"]


def test_a_stroke_type_with_an_option_is_written_as_its_base_type_and_the_option() -> None:
    square = ((10.0, 10.0), (60.0, 10.0), (60.0, 60.0), (10.0, 60.0))
    drawing = gw.Drawing(
        "u4e00-x",
        tuple(gw.Contour(square, k, ()) for k in range(3)),
        (gw.Stroke(1, (0,)), gw.Stroke(103, (1,)), gw.Stroke(101, (2,))),
        (),
        None,
        (),
    )
    record = O.glyph_of(FONT, "name.u4e00-x", drawing).record()
    assert record["strokes"] == [
        {"type": 1, "contours": [0]},
        {"type": 3, "option": 1, "contours": [1]},
        {"type": 1, "option": 1, "contours": [2]},
    ]
    validate("outlines", {**O_head(), "glyphs": {"name.u4e00-x": record}})


def O_head() -> dict[str, object]:
    return outline_head(FONT, {"licence": "LicenseRef-GlyphWiki", "copyright": "GlyphWiki"})
