import gzip
import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from han_decompose import release, tsv
from han_decompose.schema import Json
from han_decompose.store import dumps, write

from .conftest import FONT, GOLDEN

ROW = {
    "component": "bs:42",
    "kind": "babelstone",
    "text": "{42}",
    "relation": "same",
    "target": "u:F2D4",
    "basis": "IDS.TXT note 6",
    "tier": "source",
    "source": "babelstone",
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


def test_a_release_holds_the_runs_files_tables_indexes_and_terms(tmp_path: Path) -> None:
    built, manifest = build(tmp_path / "out", [golden(tmp_path / "run")])
    out = tmp_path / "out"
    assert built.problems == []
    names = {row["path"] for row in manifest["files"]}
    assert {
        f"outlines/{FONT}/050.json.gz",
        f"cuts/{FONT}/babelstone/050.json.gz",
        "cuts.babelstone.tsv.gz",
        "skipped.babelstone.tsv.gz",
        "components.babelstone.tsv",
        "verdicts.tsv",
        "library/sans.json.gz",
        "fonts.json",
        "sources.json",
        "README.md",
        "LICENSES/OFL-1.1.txt",
        "LICENSES/LicenseRef-BabelStone-IDS.txt",
    } <= names
    assert "LICENSES/CC-BY-SA-3.0.txt" not in names
    table = gzip.decompress((out / "cuts.babelstone.tsv.gz").read_bytes()).decode("utf-8")
    name, version, rows = tsv.read_table(table)
    assert (name, version) == ("cuts", "v0.0.1")
    (table_file,) = GOLDEN.glob("cuts*.tsv")
    assert rows == tsv.read_table(table_file.read_text(encoding="utf-8"))[2]
    library = json.loads(gzip.decompress((out / "library" / "sans.json.gz").read_bytes()))["library"]
    assert library["u:5C71"] == {"T": [f"{FONT}/U+50AC~babelstone.9d9dea39~1.0"]}
    counts = manifest["counts"][FONT]["babelstone"]
    assert counts == {"readings": 1, "skipped": 1, "cuts": {"accepted": 3}, "components": 3}
    assert manifest["tool"]["commit"] == "abc1234" and manifest["release"] == "v0.0.1"
    for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ")
        assert hashlib.sha256((out / path).read_bytes()).hexdigest() == digest
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "Noto Sans CJK JP 2.004, OFL-1.1" in readme and "BabelStone IDS by Andrew West" in readme
    assert "No cut in this release was made along a guide." in readme
    with pytest.raises(ValueError, match="is not empty"):
        release.Release(out, "v0.0.2")


def test_a_font_that_gives_outlines_alone_is_named_with_its_licence(tmp_path: Path) -> None:
    run = golden(tmp_path / "run")
    head = {"format": "han-decompose/outlines@1.0", "font": "babelstone-han-pua@1.472", "licence": "Arphic-1999"}
    square = {
        "contours": [["MLLL", [0, 0, 0, 100, 100, 100, 100, 0]]],
        "pieces": [[0]],
        "box": [0, 0, 1, 1],
        "advance": 1000,
    }
    file = {
        **head,
        "copyright": "(c) Arphic Technology, Andrew West.",
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
    path = second / "cuts" / FONT / "babelstone" / "050.json.gz"
    content = json.loads(gzip.decompress(path.read_bytes()))
    (kept,) = content["readings"]
    content["skipped"].append({key: kept[key] for key in ("subject", "glyph", "description", "ids")})
    content["skipped"][-1]["reason"] = {"code": "ambiguous", "text": "two readings fit equally well"}
    content["readings"][0]["method"]["tool"] = "another"
    write(path, dumps(content))
    merged = release.merge_cuts([first / "cuts" / FONT / "babelstone" / "050.json.gz", path])
    assert [row["method"]["tool"] for row in merged["readings"]] == ["hand"]
    assert [row["reason"]["code"] for row in merged["skipped"]] == ["too-few-pieces"]
    other = release.merge_cuts([path, first / "cuts" / FONT / "babelstone" / "050.json.gz"])
    assert [row["method"]["tool"] for row in other["readings"]] == ["another"]
    outline = second / "outlines" / FONT / "050.json.gz"
    changed = json.loads(gzip.decompress(outline.read_bytes()))
    changed["glyphs"]["U+50AC"]["advance"] = 999
    write(outline, dumps(changed))
    with pytest.raises(ValueError, match="differs from an earlier run"):
        release.merge_outlines([first / "outlines" / FONT / "050.json.gz", outline])


def test_a_release_packs_to_one_archive_per_font_and_source(tmp_path: Path) -> None:
    build(tmp_path / "out", [golden(tmp_path / "run")])
    made = release.pack(tmp_path / "out", tmp_path / "dist")
    names = {path.name for path in made}
    assert {
        "outlines.noto-sans-cjk-jp-2.004.tar.gz",
        "cuts.noto-sans-cjk-jp-2.004.babelstone.tar.gz",
        "licenses.tar.gz",
        "library.tar.gz",
        "cuts.babelstone.tsv.gz",
        "manifest.json",
        "README.md",
        "SHA256SUMS",
        "SHA256SUMS.assets",
    } <= names
    with tarfile.open(tmp_path / "dist" / "cuts.noto-sans-cjk-jp-2.004.babelstone.tar.gz") as archive:
        assert archive.getnames() == [f"cuts/{FONT}/babelstone/050.json.gz"]
    again = release.pack(tmp_path / "out", tmp_path / "again")
    assert all(path.read_bytes() == (tmp_path / "again" / path.name).read_bytes() for path in made)
    assert len(again) == len(made)
