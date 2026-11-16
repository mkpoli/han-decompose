import gzip
import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from han_decompose import release, tsv
from han_decompose.schema import Json, problems
from han_decompose.store import dumps, write

from .conftest import FONT, GOLDEN

ROW = {
    "component": "aj1:1815",
    "kind": "adobe-japan1",
    "text": "",
    "relation": "glyph-of",
    "target": "u:5F62",
    "basis": "Adobe-Japan1 CID order",
    "tier": "derived",
}


def golden(folder: Path) -> Path:
    """The golden files as the folder of a cutting run."""
    for path in sorted(GOLDEN.rglob("*.json")):
        name = path.relative_to(GOLDEN).as_posix() + ".gz"
        write(folder / name, dumps(json.loads(path.read_text(encoding="utf-8"))))
    return folder


def build(out: Path, runs: list[Path]) -> tuple[release.Release, Json]:
    built = release.Release(out, "v0.0.1")
    built.shards(runs)
    built.indexes()
    built.flat([ROW])
    return built, built.finish("abc1234")


def test_a_release_holds_the_runs_files_tables_indexes_and_licences(tmp_path: Path) -> None:
    built, manifest = build(tmp_path / "out", [golden(tmp_path / "run")])
    out = tmp_path / "out"
    assert built.problems == []
    names = {row["path"] for row in manifest["files"]}
    assert {
        f"outlines/{FONT}/050.json.gz",
        f"cuts/{FONT}/050.json.gz",
        "cuts.tsv.gz",
        "drawn.tsv.gz",
        "structures.tsv.gz",
        "skipped.tsv.gz",
        "components.tsv",
        "classes.tsv",
        "verdicts.tsv",
        "fonts.json",
        "README.md",
        "LICENSES/OFL-1.1.txt",
        "LICENSES/CC0-1.0.txt",
    } <= names
    assert "sources.json" not in names and not [name for name in names if "babelstone" in name]
    for name, golden_name in (
        ("cuts", "cuts"),
        ("drawn", "drawn"),
        ("structures", "structures"),
        ("skipped", "skipped"),
    ):
        table = gzip.decompress((out / f"{name}.tsv.gz").read_bytes()).decode("utf-8")
        found, version, rows = tsv.read_table(table)
        assert (found, version) == (name, "v0.0.1")
        assert rows == tsv.read_table((GOLDEN / f"{golden_name}.tsv").read_text(encoding="utf-8"))[2]
    assert tsv.read_table((out / "components.tsv").read_text(encoding="utf-8"))[2] == [ROW]
    assert tsv.read_table((out / "classes.tsv").read_text(encoding="utf-8"))[2] == []
    assert manifest["counts"][FONT] == {
        "readings": 2,
        "skipped": 1,
        "cuts": {"accepted": 4},
        "structures": 1,
        "classes": 4,
    }
    assert problems("manifest", manifest) == []
    assert manifest["tool"]["commit"] == "abc1234" and manifest["release"] == "v0.0.1"
    for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ")
        assert hashlib.sha256((out / path).read_bytes()).hexdigest() == digest
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "Noto Sans CJK JP 2.004, OFL-1.1" in readme and "© 2014-2021 Adobe" in readme
    assert "Every other file is label data under CC0-1.0" in readme.replace("\n", " ")
    assert "By status, over all fonts: 4 accepted." in readme
    assert "No cut in this release has been judged by a person." in readme
    fonts = json.loads((out / "fonts.json").read_text(encoding="utf-8"))
    assert problems("fonts", fonts) == [] and {row["id"] for row in fonts["designs"]} >= {"source-han-sans"}
    with pytest.raises(ValueError, match="is not empty"):
        release.Release(out, "v0.0.2")


def test_a_font_that_gives_outlines_alone_is_named_with_its_licence(tmp_path: Path) -> None:
    run = golden(tmp_path / "run")
    head = {"format": "han-decompose/outlines@2.0", "font": "babelstone-han-pua@1.472", "licence": "Arphic-1999"}
    square = {
        "contours": [["MLLL", [0, 0, 0, 100, 100, 100, 100, 0]]],
        "pieces": [[0]],
        "box": [0, 0, 1, 1],
        "advance": 1000,
    }
    file = {
        **head,
        "copyright": "(c) Arphic Technology, Andrew West.",
        "notice": "Outlines of BabelStone Han PUA 1.472, changed by han-decompose: a selection of its glyphs.",
        "em": 1000,
        "q": 100,
        "glyphs": {"U+F2D4": square},
    }
    write(run / "outlines" / "babelstone-han-pua@1.472" / "0f2.json.gz", dumps(file))
    built, manifest = build(tmp_path / "out", [run])
    assert built.problems == []
    assert "LICENSES/Arphic-1999.txt" in {row["path"] for row in manifest["files"]}
    assert "BabelStone Han PUA 1.472, Arphic-1999" in (tmp_path / "out" / "README.md").read_text(encoding="utf-8")


def test_the_first_run_given_stands_and_a_skip_gives_way_to_a_reading(tmp_path: Path) -> None:
    first, second = golden(tmp_path / "first"), golden(tmp_path / "second")
    one = first / "cuts" / FONT / "050.json.gz"
    path = second / "cuts" / FONT / "050.json.gz"
    content = json.loads(gzip.decompress(path.read_bytes()))
    kept = content["readings"][0]
    content["skipped"].append({key: kept[key] for key in ("subject", "glyph", "layer", "structure", "text")})
    content["skipped"][-1]["reason"] = {"code": "ambiguous", "text": "two readings fit equally well"}
    content["readings"][0]["method"]["tool"] = "another"
    write(path, dumps(content))
    merged = release.merge_cuts([one, path])
    assert [row["method"]["tool"] for row in merged["readings"]] == ["hand", "hand"]
    assert [row["reason"]["code"] for row in merged["skipped"]] == ["too-few-pieces"]
    other = release.merge_cuts([path, one])
    assert [row["method"]["tool"] for row in other["readings"]] == ["another", "hand"]
    outline = second / "outlines" / FONT / "050.json.gz"
    changed = json.loads(gzip.decompress(outline.read_bytes()))
    changed["glyphs"]["U+50AC"]["advance"] = 999
    write(outline, dumps(changed))
    with pytest.raises(ValueError, match="differs from an earlier run"):
        release.merge_outlines([first / "outlines" / FONT / "050.json.gz", outline])


def test_another_method_reads_the_same_structure_beside_the_first(tmp_path: Path) -> None:
    first, second = golden(tmp_path / "first"), golden(tmp_path / "second")
    path = second / "cuts" / FONT / "050.json.gz"
    content = json.loads(gzip.decompress(path.read_bytes()))
    again = content["readings"][0]
    again["method"] = {"name": "deal", "tool": "han-decompose", "grain": "piece"}
    for cut in again["cuts"]:
        cut["id"] = cut["id"].replace("-hand:", "-deal:")
    content["readings"] = [again]
    content["readings"][0]["layer"] = []
    write(path, dumps(content))
    merged = release.merge_cuts([first / "cuts" / FONT / "050.json.gz", path])
    root = [row for row in merged["readings"] if row["layer"] == []]
    assert {row["method"]["name"] for row in root} == {"hand", "deal"}
    assert [row["chosen"] for row in root].count(True) == 1


def test_the_command_builds_and_packs_and_refuses_a_run_that_is_not_there(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from han_decompose import pins
    from han_decompose.cli import app

    try:
        pins.source_paths(pins.source("adobe-japan1"), fetch=False)
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    run = golden(tmp_path / "run")
    arguments = ["release", str(tmp_path / "out"), "v0.0.1", "--run", str(run), "--dist", str(tmp_path / "dist")]
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 0, result.output
    assert f"{FONT}\treadings 2\taccepted 4\tclasses 4" in result.output
    assert (tmp_path / "dist" / "components.tsv").exists() and (tmp_path / "dist" / "SHA256SUMS.assets").exists()
    missing = ["release", str(tmp_path / "other"), "v0.0.1", "--run", str(tmp_path / "nowhere")]
    result = CliRunner().invoke(app, missing)
    assert result.exit_code == 1 and "is not the folder of a run" in result.output
    again = CliRunner().invoke(
        app, ["release", str(tmp_path / "third"), "v0.0.1", "--run", str(run), "--dist", str(tmp_path / "dist")]
    )
    assert again.exit_code == 1 and "is not empty" in again.output


def test_a_release_packs_to_one_archive_per_font_and_kind(tmp_path: Path) -> None:
    build(tmp_path / "out", [golden(tmp_path / "run")])
    made = release.pack(tmp_path / "out", tmp_path / "dist")
    names = {path.name for path in made}
    assert {
        "outlines.noto-sans-cjk-jp-2.004.tar.gz",
        "cuts.noto-sans-cjk-jp-2.004.tar.gz",
        "licenses.tar.gz",
        "cuts.tsv.gz",
        "manifest.json",
        "README.md",
        "SHA256SUMS",
        "SHA256SUMS.assets",
    } <= names
    with tarfile.open(tmp_path / "dist" / "cuts.noto-sans-cjk-jp-2.004.tar.gz") as archive:
        assert archive.getnames() == [f"cuts/{FONT}/050.json.gz"]
    again = release.pack(tmp_path / "out", tmp_path / "again")
    assert all(path.read_bytes() == (tmp_path / "again" / path.name).read_bytes() for path in made)
    assert len(again) == len(made)
