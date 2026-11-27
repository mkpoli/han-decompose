import base64
import gzip
import hashlib
import json
import struct
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from han_decompose import identifiers as I
from han_decompose import pins
from han_decompose.cli import app
from han_decompose.importers import composer_export as X
from han_decompose.outline import Chain, Face
from han_decompose.schema import Json

from .fonts import build, pinned_chain, row

FIXTURES = Path(__file__).parent / "fixtures" / "composer-export"


def packed(units: Sequence[float]) -> str:
    """Points as an export writes them: int16 in quarter units, little-endian, base64."""
    return base64.b64encode(struct.pack(f"<{len(units)}h", *(round(value * 4) for value in units))).decode()


def glyph(v: int, *contours: tuple[str, Sequence[float]]) -> Json:
    return {
        "G": {
            "v": v,
            "b": [0, 0, 0, 0],
            "p": [[letters, packed(units), packed([0] * len(units))] for letters, units in contours],
        }
    }


# What han-compose records for the glyphs of the test fonts: 512 of 1024 units is 500 units.
SQUARE = ("MLLL", [0, 0, 0, 500, 500, 500, 500, 0])
HALF = ("MLLL", [0, 0, 0, 250, 500, 250, 500, 0])
SMALL = ("MLLL", [0, 0, 0, 250, 250, 250, 250, 0])
RING = ("Q4*", [0, 0, 0, 15.625, 15.625, 15.625, 15.625, 0])


@pytest.fixture
def chain(tmp_path: Path) -> Chain:
    faces = []
    for name, upem, extra in (("first", 1024, None), ("second", 2048, {0x5C71: "square"})):
        path = build(tmp_path / f"{name}.ttf", upem, extra)
        faces.append(Face({**row(f"{name}@1", upem), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, path))
    return Chain("test", faces)


def write(folder: Path, chain: Chain, records: dict[str, Json], **about: object) -> Path:
    """An export folder holding `records` by key, half its shards compressed."""
    digests = {face.id: face.row["sha256"] for face in chain.faces}
    shards: dict[str, dict[str, Json]] = {}
    for key, record in records.items():
        shards.setdefault(X.key_hash(key)[:3], {})[X.key_hash(key)] = record
    counts = {"records": {"entries": len(records), "files": len(shards)}}
    manifest = {"format": 6, "quant": 4, "composer": {"font_sha256": digests}, "files": counts, **about}
    (folder / "g").mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for index, (name, shard) in enumerate(sorted(shards.items())):
        data = json.dumps(shard).encode()
        (folder / "g" / f"{name}.json").write_bytes(gzip.compress(data) if index % 2 else data)
    return folder


def records() -> dict[str, Json]:
    return {
        "一": glyph(1, SQUARE),
        "一\U000e0100": glyph(1, HALF),
        "〇": glyph(1, RING),
        "山": glyph(0, SMALL),
        "⿰一山": {"s": "a sequence has no glyph"},
    }


def test_a_record_is_read_as_commands_and_quarter_units() -> None:
    assert X.recorded(glyph(1, SQUARE, RING)["G"]) == [
        ("MLLL", [0, 0, 0, 2000, 2000, 2000, 2000, 0]),
        ("Q4*", [0, 0, 0, 62, 62, 62, 62, 0]),
    ]
    assert X.coarsened([("MLLL", [0, 0, 0, 50000, 50000, 50000, 50000, 0])], 4) == [
        X.recorded(glyph(1, SQUARE)["G"])[0]
    ]
    assert X.coarsened([("ML", [1562, -1562, 1563, 13])], 4) == [("ML", [62, -62, 63, 1])]


def test_an_export_written_from_the_same_fonts_is_reproduced(tmp_path: Path, chain: Chain) -> None:
    result = X.parity(write(tmp_path / "export", chain, records()), chain)
    assert (result.shards, result.records, result.glyphs, result.compared, result.same) == (5, 5, 4, 4, 4)
    assert result.complete and result.exact and not result.different and not result.other_face


def test_a_moved_point_is_found(tmp_path: Path, chain: Chain) -> None:
    moved = records()
    moved["山"] = glyph(0, ("MLLL", [0, 0, 0, 250, 250, 250.25, 250, 0]))
    result = X.parity(write(tmp_path / "export", chain, moved), chain)
    assert result.different == ["U+5C71"] and result.same == 3 and not result.exact


def test_contours_in_another_order_are_found(tmp_path: Path, chain: Chain) -> None:
    pair = chain.faces[0].contours("U+4E8C") or []
    as_recorded = [(letters, [value / 100 for value in points]) for letters, points in pair]
    right, swapped = records(), records()
    right["二"], swapped["二"] = glyph(1, *as_recorded), glyph(1, *reversed(as_recorded))
    assert X.parity(write(tmp_path / "right", chain, right), chain).exact
    assert X.parity(write(tmp_path / "swapped", chain, swapped), chain).different == ["U+4E8C"]


def test_a_glyph_taken_from_another_font_is_found(tmp_path: Path, chain: Chain) -> None:
    other = records()
    other["山"] = glyph(1, SMALL)
    result = X.parity(write(tmp_path / "export", chain, other), chain)
    assert result.other_face == ["U+5C71"] and result.same == 4 and not result.exact


def test_a_glyph_record_no_selector_reaches_is_counted(tmp_path: Path, chain: Chain) -> None:
    more = records()
    more["催"] = glyph(1, SQUARE)
    result = X.parity(write(tmp_path / "export", chain, more), chain)
    assert (result.glyphs, result.compared, result.same) == (5, 4, 4) and not result.exact


def test_named_shards_alone_are_read(tmp_path: Path, chain: Chain) -> None:
    export = write(tmp_path / "export", chain, records())
    absent = next(name for name in ("fff", "ffe") if not (export / "g" / f"{name}.json").exists())
    result = X.parity(export, chain, [X.key_hash("山")[:3], absent])
    assert (result.shards, result.glyphs, result.compared, result.same) == (1, 1, 1, 1) and result.exact
    assert not X.parity(export, chain, [absent]).exact
    for name in ("zzz", "ABC", "0", "../g"):
        with pytest.raises(ValueError, match="three lower-case hex digits"):
            X.parity(export, chain, [name])


def test_an_export_that_lost_a_shard_is_not_reproduced(tmp_path: Path, chain: Chain) -> None:
    export = write(tmp_path / "export", chain, records())
    (export / "g" / f"{X.key_hash('山')[:3]}.json").unlink()
    result = X.parity(export, chain)
    assert (result.shards, result.records, result.stated) == (4, 4, (5, 5))
    assert result.glyphs == result.compared == result.same == 3 and not result.complete and not result.exact
    for path in (export / "g").iterdir():
        path.unlink()
    assert not X.parity(export, chain).exact


def test_an_export_without_a_glyph_record_is_not_reproduced(tmp_path: Path, chain: Chain) -> None:
    result = X.parity(write(tmp_path / "export", chain, {"⿰一山": {"s": "a sequence has no glyph"}}), chain)
    assert result.complete and result.glyphs == 0 and not result.exact


def test_an_export_of_other_fonts_or_another_format_is_refused(tmp_path: Path, chain: Chain) -> None:
    with pytest.raises(ValueError, match="format 5"):
        X.parity(write(tmp_path / "old", chain, records(), format=5), chain)
    other = write(tmp_path / "other", chain, records(), composer={"font_sha256": {"first@1": "0" * 64}})
    with pytest.raises(ValueError, match="other font files"):
        X.parity(other, chain)
    with pytest.raises(ValueError, match="does not state 'font_sha256'"):
        X.parity(write(tmp_path / "bare", chain, records(), composer={}), chain)
    with pytest.raises(ValueError, match="has no manifest.json"):
        X.parity(tmp_path / "absent", chain)


def test_the_parity_command_fails_on_a_difference(
    tmp_path: Path, chain: Chain, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Chain, "pinned", classmethod(lambda cls, name, cache=None, fetch=False: chain))
    good = CliRunner().invoke(app, ["parity", str(write(tmp_path / "good", chain, records()))])
    assert good.exit_code == 0 and "identical\t4" in good.stdout
    moved = records()
    moved["一"] = glyph(1, HALF)
    bad = CliRunner().invoke(app, ["parity", str(write(tmp_path / "bad", chain, moved))])
    assert bad.exit_code == 1 and "different\t1\tU+4E00" in bad.stdout
    absent = CliRunner().invoke(app, ["parity", str(tmp_path / "absent")])
    assert (
        absent.exit_code == 1 and "has no manifest.json" in absent.output and absent.exception.__class__ is SystemExit
    )
    (tmp_path / "good" / "g" / f"{X.key_hash('山')[:3]}.json").unlink()
    short = CliRunner().invoke(app, ["parity", str(tmp_path / "good")])
    assert short.exit_code == 1 and "shards\t4\tof 5" in short.stdout


#: The designs each export was written from, in the order of its chain.
DESIGNS = {"sans": ["source-han-sans", "plangothic"], "serif": ["source-han-serif"]}


@pytest.mark.parametrize("name", ["sans", "serif"])
def test_the_pinned_fonts_draw_what_han_compose_exported(name: str) -> None:
    fixture = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    chain = pinned_chain(*DESIGNS[name])
    assert {record["font"] for record in fixture["records"].values()} == {
        font["id"] for design in DESIGNS[name] for font in pins.chain(design)
    }
    for selector, record in fixture["records"].items():
        face = chain.face(selector)
        assert face is not None and face.id == record["font"], selector
        assert record["v"] == (1 if face is chain.faces[0] else 0), selector
        drawn = X.coarsened(face.contours(selector) or [], fixture["quant"])
        assert drawn == X.recorded({"p": [[*contour, ""] for contour in record["p"]]}), selector
    assert any(I.selected(selector) and len(I.selected(selector) or "") == 2 for selector in fixture["records"])


def test_format_7_export_parity_is_reproduced(tmp_path: Path, chain: Chain) -> None:
    """Format 7 files shards under `g/<hh>/<hhhh>.json` keyed by raw character rather than SHA-256."""
    digests = {face.id: face.row["sha256"] for face in chain.faces}
    shards: dict[str, dict[str, Json]] = {}
    for key, record in records().items():
        shards.setdefault(X.key_hash(key)[:4], {})[key] = record
    folder = tmp_path / "export-v7"
    manifest = {
        "format": 7,
        "quant": 4,
        "composer": {"font_sha256": digests},
        "files": {"records": {"entries": len(records()), "files": len(shards)}},
    }
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, content in shards.items():
        path = folder / "g" / name[:2] / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    result = X.parity(folder, chain)
    assert (result.shards, result.records, result.glyphs, result.compared, result.same) == (5, 5, 4, 4, 4)
    assert result.complete and result.exact and not result.different and not result.other_face
    one = X.parity(folder, chain, [X.key_hash("山")[:4]])
    assert (one.shards, one.glyphs, one.compared, one.same) == (1, 1, 1, 1) and one.exact
    with pytest.raises(ValueError, match="four lower-case hex digits"):
        X.parity(folder, chain, ["abc"])
