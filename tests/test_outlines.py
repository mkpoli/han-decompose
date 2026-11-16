import gzip
import json
from pathlib import Path

import pytest
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
    blocks = ["04e", "04f", "050", "051", "052", "053"]
    for workers in (1, 3):
        done = list(outlines.run(FONT, tmp_path / str(workers), workers, only=blocks))
        assert [block.block for block in done] == blocks and all(block.failed == [] for block in done)
        file = read(tmp_path / str(workers) / "outlines" / FONT / "050.json.gz")
        assert problems("outlines", file) == []
        assert {selector: file["glyphs"][selector] for selector in golden["glyphs"]} == golden["glyphs"]
    names = sorted(path.name for path in (tmp_path / "1" / "outlines" / FONT).iterdir())
    assert names == [f"{block}.json.gz" for block in blocks]
    for name in names:
        one = (tmp_path / "1" / "outlines" / FONT / name).read_bytes()
        assert one == (tmp_path / "3" / "outlines" / FONT / name).read_bytes(), name


def test_a_block_with_a_glyph_that_failed_is_read_again_and_the_command_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawing = Drawing(Face(ROW, build(tmp_path / "test.ttf")))
    real = drawing.glyph
    broken = {"on": True}

    def glyph(selector: str) -> object:
        if selector == "U+4E3F" and broken["on"]:
            raise RuntimeError("bad outline")
        return real(selector)

    monkeypatch.setattr(drawing, "glyph", glyph)
    out = tmp_path / "out"
    (first,) = outlines.dump(drawing, out, ROW, only=["04e"])
    folder = out / "outlines" / "test@1"
    assert (
        first.failed
        and (folder / "04e.failed.txt").read_text(encoding="utf-8") == "U+4E3F\tRuntimeError: bad outline\n"
    )
    (again,) = outlines.dump(drawing, out, ROW, only=["04e"])
    assert not again.kept and again.failed == first.failed
    broken["on"] = False
    (fixed,) = outlines.dump(drawing, out, ROW, only=["04e"])
    assert not fixed.kept and fixed.failed == [] and not (folder / "04e.failed.txt").exists()
    assert "U+4E3F" in read(folder / "04e.json.gz")["glyphs"]
    (kept,) = outlines.dump(drawing, out, ROW, only=["04e"])
    assert kept.kept


def test_the_command_exits_nonzero_for_a_glyph_it_could_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pinned_face(FONT)

    def fail(font: str, out: Path, workers: int, cache: object, only: object) -> list[outlines.Block]:
        return [outlines.Block(font, "050", 3, 0, [("U+50AC", "RuntimeError: bad")])]

    monkeypatch.setattr(outlines, "run", fail)
    result = CliRunner().invoke(app, ["outlines", str(tmp_path), "--font", FONT, "--blocks", "050"])
    assert result.exit_code == 1 and "U+50AC: RuntimeError: bad" in result.output


def test_the_command_writes_the_outlines_of_chosen_fonts_and_blocks(tmp_path: Path) -> None:
    pinned_face(FONT)
    result = CliRunner().invoke(app, ["outlines", str(tmp_path), "--font", FONT, "--blocks", "050", "--workers", "1"])
    assert result.exit_code == 0, result.output
    assert f"{FONT}\tglyphs " in result.stdout and (tmp_path / "outlines" / FONT / "050.json.gz").exists()
    unknown = CliRunner().invoke(app, ["outlines", str(tmp_path), "--font", "noto@9"])
    assert unknown.exit_code == 1
