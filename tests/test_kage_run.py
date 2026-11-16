import gzip
import json
from pathlib import Path

import pytest

from han_decompose import glyphwiki as gw
from han_decompose import glyphwiki_outlines as O
from han_decompose.cutters import kage_run
from han_decompose.descriptions import Table
from han_decompose.schema import problems

FIXTURES = Path(__file__).parent / "fixtures" / "glyphwiki"
FONT = "glyphwiki@20261115"


def test_names_are_grouped_by_block_in_the_order_they_are_written() -> None:
    blocks, unspelled = kage_run.block_names(["u793e-j", "u4e00", "u793e", "u845b-ue0100", "u793b-01", "u793e_x"])
    assert blocks == {"04e": ["u4e00"], "079": ["u793e", "u793b-01", "u793e-j"], "084": ["u845b-ue0100"]}
    assert unspelled == ["u793e_x"]


def test_chunks_are_runs_of_neighbouring_blocks() -> None:
    blocks = {f"{n:03x}": ["x"] * size for n, size in enumerate([5, 1, 1, 5, 2, 2])}
    parts = kage_run.chunks(blocks, 3)
    assert [b for part in parts for b in part] == list(blocks) and len(parts) <= 3


@pytest.fixture(scope="module")
def dump() -> gw.Dump:
    return gw.Dump(FIXTURES / "dump.txt", gw.DUMP_URL, 1, "0" * 64, "2026-11-15T17:01:31Z")


def test_a_block_is_written_whole_with_its_marker(tmp_path: Path, dump: gw.Dump) -> None:
    tables = Table("babelstone", names=frozenset())
    tables.add("社", "⿰礻土")
    tables.add("社", "⿰示土")
    names = ["u793a-01", "u793b-01", "u793e", "u793e-j"]
    rows = list(gw.draw_rows(names, dump.path))
    counts = kage_run.write_one("079", rows, O.font_row(dump), [tables], tmp_path)
    assert (counts.glyphs, counts.readings, counts.cuts, counts.divided, counts.attempted) == (4, 2, 4, 2, 2)
    assert counts.skipped == {"unlike-division": 2}
    outlines = json.loads(gzip.decompress((tmp_path / "outlines" / FONT / "079.json.gz").read_bytes()))
    cuts = json.loads(gzip.decompress((tmp_path / "cuts" / FONT / "079.json.gz").read_bytes()))
    assert list(outlines["glyphs"]) == ["U+793E", "name.u793a-01", "name.u793b-01", "name.u793e-j"]
    assert problems("outlines", outlines) == [] and problems("cuts", cuts, outlines) == []
    assert [r["glyph"].split("/")[1] for r in cuts["readings"]] == ["U+793E", "name.u793e-j"]
    assert (tmp_path / "blocks" / "079.json").exists()
    assert kage_run.totals(tmp_path).readings == 2


def test_every_cited_glyph_is_in_an_outline_file(tmp_path: Path, dump: gw.Dump) -> None:
    tables = Table("babelstone", names=frozenset())
    for char, text in [("社", "⿰礻土"), ("倁", "⿰亻知"), ("知", "⿰矢口"), ("\U000235b3", "⿰木䖍")]:
        tables.add(char, text)
    blocks, _ = kage_run.block_names(kage_run.dump_names(dump))
    assert "name.u458d-j@3" in {f"name.{n}" for names in blocks.values() for n in names}
    for block, names in blocks.items():
        rows = list(gw.draw_rows(names, dump))
        kage_run.write_one(block, rows, O.font_row(dump), [tables], tmp_path)
    held: set[str] = set()
    for path in (tmp_path / "outlines" / FONT).glob("*.json.gz"):
        held.update(json.loads(gzip.decompress(path.read_bytes()))["glyphs"])
    cited: set[str] = set()
    for path in (tmp_path / "cuts" / FONT).glob("*.json.gz"):
        for reading in json.loads(gzip.decompress(path.read_bytes()))["readings"]:
            cited.update(c["style"]["glyph"].split("/")[1] for c in reading["cuts"] if "glyph" in c.get("style", {}))
    assert {"name.u571f-j", "name.u793b-01", "name.u458d-j@3"} <= cited
    assert cited <= held
