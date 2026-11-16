import gzip
import json
from pathlib import Path

import pytest

from han_decompose import descriptions, ids, pins
from han_decompose.cutters import library
from han_decompose.descriptions import Table
from han_decompose.pieces import Drawing
from han_decompose.schema import problems
from han_decompose.store import Store

from .fonts import pinned_chain


def table() -> Table:
    out = Table("babelstone")
    for char, text in {"催": "⿰亻崔", "崔": "⿱山隹", "隹": "隹", "山": "山", "回": "⿴囗口", "囗": "⿴囗口"}.items():
        out.add(char, text)
    return out


def test_a_leaf_opens_into_its_components_own_description() -> None:
    opening = library.opener(table())
    inside = opening(ids.Node("崔"), ("催",))
    assert inside is not None and inside.text == "崔" and inside.operator == "⿱" and inside.opened == "⿱山隹"
    assert [child.text for child in inside.children] == ["山", "隹"]
    assert opening(ids.Node("山"), ("催",)) is None
    assert opening(ids.Node("隹"), ("催",)) is None
    assert opening(ids.Node("囗"), ("回", "囗")) is None
    assert opening(ids.Node("崔"), tuple("abcdefgh")) is None
    assert opening(ids.Node("{42}"), ("催",)) is None


def pinned() -> tuple[Table, list[Drawing]]:
    try:
        return descriptions.table("babelstone"), [
            Drawing(face) for face in pinned_chain("source-han-sans", "plangothic").faces
        ]
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")


def test_a_glyph_is_cut_as_deep_as_its_pieces_allow() -> None:
    found, drawings = pinned()
    store, counts = Store(), library.Counts()
    description = found.first("催")
    assert description is not None
    library.one(description, drawings, found, store, counts)
    ((_, readings),) = store.readings.items()
    row, inner = readings
    assert row["tree"] == "⿰亻⿱山隹" and [node["member"] for node in row["opened"]] == ["u:5D14"]
    assert inner["subject"] == "u:5D14" and inner["layer"] == [row["cuts"][1]["id"].rsplit("~", 1)[1]]
    assert [(cut["class"], cut["contours"], cut["status"]) for cut in [*row["cuts"], *inner["cuts"]]] == [
        ("u:4EBB", [9, 10], "accepted"),
        ("u:5D14", [0, 1, 2, 3, 4, 5, 6, 7, 8], "accepted"),
        ("u:5C71", [0, 2], "accepted"),
        ("u:96B9", [1, 3, 4, 5, 6, 7, 8], "accepted"),
    ]
    leaves = [row["cuts"][0], *inner["cuts"]]
    assert all({"filled", "skeleton"} <= set(cut["checks"]) for cut in leaves)
    assert [cut["calibrated"] for cut in leaves] == [False, "u:5C71", False]
    assert counts.readings == 1 and counts.cuts == {"accepted": 4} and len(counts.against) >= 3
    # 偹 has fewer pieces than operands: nothing is dealt, and the attempt is kept with its reason.
    other = found.first("偹")
    assert other is not None
    library.one(other, drawings, found, store, counts)
    ((_, skipped),) = store.skipped.items()
    assert [row["reason"]["code"] for row in skipped] == ["too-few-pieces"] and counts.skipped == {"too-few-pieces": 1}
    # 一 is written as itself: there is nothing to cut and no row.
    whole = found.first("一")
    assert whole is not None
    library.one(whole, drawings, found, store, counts)
    assert counts.readings == 1 and sum(counts.skipped.values()) == 1


def test_an_opening_that_fails_further_down_leaves_the_leaf_whole() -> None:
    _, drawings = pinned()
    wrong = Table("babelstone")
    for char, text in {"催": "⿰亻崔", "崔": "⿱山⿰隹山", "隹": "隹", "山": "山", "亻": "亻"}.items():
        wrong.add(char, text)
    store, counts = Store(), library.Counts()
    description = wrong.first("催")
    assert description is not None
    library.one(description, drawings, wrong, store, counts)
    ((_, readings),) = store.readings.items()
    (row,) = readings
    # 崔 deals into 山 and a rest, but the rest is one piece and cannot be 隹 beside 山: the
    # opening is dropped whole and 崔 stays a leaf.
    assert row["tree"] == "⿰亻崔" and "opened" not in row and len(readings) == 1
    assert [(cut["class"], cut["contours"]) for cut in row["cuts"]] == [
        ("u:4EBB", [9, 10]),
        ("u:5D14", [0, 1, 2, 3, 4, 5, 6, 7, 8]),
    ]
    assert counts.skipped == {} and row["evidence"]["likeness"] == min(cut["evidence"]["fit"] for cut in row["cuts"])


def test_a_block_is_written_once_and_a_second_run_goes_on_after_it(tmp_path: Path) -> None:
    pinned()
    ((block, counts),) = list(
        library.run(["source-han-sans", "plangothic"], "babelstone", tmp_path, workers=1, only=["050"])
    )
    assert block == "050" and counts.readings > 200 and counts.cuts["accepted"] > 400
    marker = json.loads((tmp_path / "blocks" / "050.json").read_text(encoding="utf-8"))
    assert marker["readings"] == counts.readings and marker["against"]
    assert list(library.run(["source-han-sans", "plangothic"], "babelstone", tmp_path, workers=1, only=["050"])) == []
    added = library.named(tmp_path, ["source-han-sans", "plangothic"])
    assert added > 0 and library.named(tmp_path, ["source-han-sans", "plangothic"]) == 0
    files = {
        path.relative_to(tmp_path).as_posix(): json.loads(gzip.decompress(path.read_bytes()))
        for path in tmp_path.rglob("*.json.gz")
    }
    for name, content in files.items():
        kind, font, *_ = name.split("/")
        outlines = files.get(f"outlines/{font}/{name.split('/')[-1]}") if kind == "cuts" else None
        assert problems(kind, content, outlines) == [], name
    cuts = files["cuts/noto-sans-cjk-jp@2.004/050.json.gz"]
    against = {
        check["against"] for row in cuts["readings"] for cut in row["cuts"] for check in cut.get("checks", {}).values()
    }
    for glyph in against:
        font, selector = glyph.split("/")
        shard = f"{int(selector[2:], 16) >> 8:03x}"
        assert selector in files[f"outlines/{font}/{shard}.json.gz"]["glyphs"], glyph
