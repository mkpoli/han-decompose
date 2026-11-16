import gzip
import json
from pathlib import Path

from typer.testing import CliRunner

from han_decompose import outlines
from han_decompose.cli import app
from han_decompose.outline import Face
from han_decompose.pieces import Drawing
from han_decompose.schema import Json, problems

from .conftest import FONT, GOLDEN
from .fonts import build, pinned_face

ROW: Json = {
    "id": "test@1",
    "name": "Test",
    "version": "1",
    "upem": 1024,
    "licence": "OFL-1.1",
    "copyright": "Copyright Test",
}


def read(path: Path) -> Json:
    value: Json = json.loads(gzip.decompress(path.read_bytes()))
    return value


def test_every_glyph_a_font_maps_is_written_in_the_file_of_its_block(tmp_path: Path) -> None:
    drawing = Drawing(Face(ROW, build(tmp_path / "test.ttf")))
    done = list(outlines.dump(drawing, tmp_path / "out", ROW))
    assert [(block.block, block.written, block.empty) for block in done] == [
        ("000", 0, 1),
        ("030", 1, 0),
        ("04e", 5, 0),
    ]
    files = {path.name: read(path) for path in (tmp_path / "out" / "outlines" / "test@1").glob("*.json.gz")}
    assert sorted(files) == ["030.json.gz", "04e.json.gz"]
    assert list(files["04e.json.gz"]["glyphs"]) == ["U+4E00", "U+4E00.E0100", "U+4E00.E0101", "U+4E3F", "U+4E8C"]
    for file in files.values():
        assert problems("outlines", file) == [] and file["licence"] == "OFL-1.1" and file["font"] == "test@1"
    pair = files["04e.json.gz"]["glyphs"]["U+4E8C"]
    assert pair["pieces"] == [[0], [1]] and len(pair["contours"]) == 2


def test_a_block_that_is_there_is_left_as_it_is(tmp_path: Path) -> None:
    drawing = Drawing(Face(ROW, build(tmp_path / "test.ttf")))
    list(outlines.dump(drawing, tmp_path / "out", ROW))
    path = tmp_path / "out" / "outlines" / "test@1" / "04e.json.gz"
    before = path.read_bytes()
    again = list(outlines.dump(drawing, tmp_path / "out", ROW, only=["04e"]))
    assert [(block.block, block.kept, block.written) for block in again] == [("04e", True, 0)]
    assert path.read_bytes() == before
    assert not list(path.parent.glob(".*.part"))


def test_the_pinned_instance_of_a_variable_font_is_the_one_read(tmp_path: Path) -> None:
    row = {**ROW, "instance": {"wght": 900}}
    face = Face(row, build(tmp_path / "test.ttf", variable=True))
    list(outlines.dump(Drawing(face), tmp_path / "out", row, only=["04e"]))
    glyphs = read(tmp_path / "out" / "outlines" / "test@1" / "04e.json.gz")["glyphs"]
    assert glyphs["U+4E00"]["box"][3] == 1000


def test_a_glyph_that_cannot_be_read_is_reported_and_the_rest_is_written(tmp_path: Path) -> None:
    drawing = Drawing(Face(ROW, build(tmp_path / "test.ttf")))
    broken = drawing.glyph

    def glyph(selector: str) -> object:
        if selector == "U+4E3F":
            raise RuntimeError("bad outline")
        return broken(selector)

    drawing.glyph = glyph  # type: ignore[method-assign,assignment]
    (block,) = outlines.dump(drawing, tmp_path / "out", ROW, only=["04e"])
    assert block.failed == [("U+4E3F", "RuntimeError: bad outline")] and block.written == 4
    assert "U+4E3F" not in read(tmp_path / "out" / "outlines" / "test@1" / "04e.json.gz")["glyphs"]


def test_a_pinned_font_gives_the_golden_outline_whatever_the_number_of_processes(tmp_path: Path) -> None:
    pinned_face(FONT)
    golden = json.loads((GOLDEN / "outlines" / FONT / "050.json").read_text(encoding="utf-8"))
    for workers in (1, 2):
        out = tmp_path / str(workers)
        (block,) = outlines.run(FONT, out, workers, only=["050"])
        assert block.failed == [] and block.written > 200
        file = read(out / "outlines" / FONT / "050.json.gz")
        assert problems("outlines", file) == []
        assert {selector: file["glyphs"][selector] for selector in golden["glyphs"]} == golden["glyphs"]
    same = [(tmp_path / str(n) / "outlines" / FONT / "050.json.gz").read_bytes() for n in (1, 2)]
    assert same[0] == same[1]


def test_the_command_writes_the_outlines_of_chosen_fonts_and_blocks(tmp_path: Path) -> None:
    pinned_face(FONT)
    result = CliRunner().invoke(app, ["outlines", str(tmp_path), "--font", FONT, "--blocks", "050", "--workers", "1"])
    assert result.exit_code == 0, result.output
    assert f"{FONT}\tglyphs " in result.stdout and (tmp_path / "outlines" / FONT / "050.json.gz").exists()
    unknown = CliRunner().invoke(app, ["outlines", str(tmp_path), "--font", "noto@9"])
    assert unknown.exit_code == 1
