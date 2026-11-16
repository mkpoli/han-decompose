import gzip
import json
from pathlib import Path

import pytest

from han_decompose import classes, descriptions, ids, pins, structures
from han_decompose import identifiers as I
from han_decompose.cutters import reading, survey
from han_decompose.descriptions import Table
from han_decompose.pieces import Drawing
from han_decompose.schema import problems
from han_decompose.store import Store

from .fonts import pinned_chain

FIXTURES = Path(__file__).parent / "fixtures" / "survey"


def table() -> Table:
    out = Table("babelstone")
    for char, text in {
        "仙": "⿰亻山",
        "催": "⿰亻崔",
        "崔": "⿱山隹",
        "隹": "隹",
        "偹": "⿲亻丨备",
        "山": "山",
    }.items():
        out.add(char, text)
    return out


def test_the_characters_a_component_reaches_into() -> None:
    assert survey.holders(table(), "山") == {"仙", "催", "崔"}
    assert survey.holders(table(), "隹") == {"催", "崔"}
    assert survey.holders(table(), "口") == set()


def test_a_description_is_spelled_out_through_the_components_that_hold_the_target() -> None:
    found = table()
    description = found.first("催")
    assert description is not None
    offered = survey.readings(description, found, survey.holders(found, "山"), "山")
    assert [(cap, ids.spelled(root)) for cap, root in offered] == [(1, "⿰亻⿱山隹")]
    opened = offered[0][1].children[1]
    assert opened.text == "崔" and opened.opened == "⿱山隹"
    named = found.first("仙")
    assert named is not None
    assert [(cap, ids.spelled(root)) for cap, root in survey.readings(named, found, {"仙"}, "山")] == [(0, "⿰亻山")]


def pinned() -> tuple[Table, list[Drawing]]:
    try:
        return descriptions.table("babelstone"), [
            Drawing(face) for face in pinned_chain("source-han-sans", "plangothic").faces
        ]
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")


def test_a_character_is_read_at_the_deepest_tree_that_closes() -> None:
    found, drawings = pinned()
    outcomes = {outcome.char: outcome for outcome in survey.survey(found, drawings, "山", only="催仙㒞")}
    deep = outcomes["催"]
    assert deep.readings is not None and deep.opened == deep.fullest == 1
    assert deep.readings[0]["tree"] == "⿰亻⿱山隹" and len(deep.readings) == 2
    (cut,) = survey.instances(deep.readings, "山")
    assert cut["contours"] == [0, 2] and cut["path"] == [0] and cut["calibrated"] == "u:5C71"
    assert cut["id"].endswith("~9d9dea39-deal:1~a674f7d6-deal:0")
    assert set(cut["checks"]) == {"filled", "skeleton"} and list(deep.glyphs) == [deep.readings[0]["glyph"]]
    assert outcomes["仙"].opened == 0
    skipped = outcomes["㒞"].skipped
    assert skipped is not None and skipped["reason"]["code"] == "unlike-element"
    assert skipped["reason"]["text"].startswith("noto-sans-cjk-jp@2.004, 1 component deep:")


def test_what_a_survey_finds_is_written_as_files_of_the_format(tmp_path: Path) -> None:
    found, drawings = pinned()
    store = Store()
    for outcome in survey.survey(found, drawings, "山", only="催仙㒞"):
        for glyph, record in outcome.glyphs.items():
            store.record(*I.split_glyph_id(glyph), record)
        for row in outcome.readings or []:
            store.reading(row)
        if outcome.skipped is not None:
            store.skip(outcome.skipped, outcome.skipped["glyph"].split("/")[0])
    files = dict(store.files())
    assert list(files) == [
        "cuts/noto-sans-cjk-jp@2.004/034.json.gz",
        "cuts/noto-sans-cjk-jp@2.004/04e.json.gz",
        "cuts/noto-sans-cjk-jp@2.004/050.json.gz",
        "outlines/noto-sans-cjk-jp@2.004/034.json.gz",
        "outlines/noto-sans-cjk-jp@2.004/04e.json.gz",
        "outlines/noto-sans-cjk-jp@2.004/050.json.gz",
    ]
    for name, content in files.items():
        if name.startswith("cuts/"):
            assert problems("cuts", content, files[name.replace("cuts/", "outlines/")]) == []
        else:
            assert problems("outlines", content) == []
    written = store.write(tmp_path)
    assert (
        len(written) == 6
        and store.write(tmp_path / "again")
        and all(path.read_bytes() == (tmp_path / "again" / path.relative_to(tmp_path)).read_bytes() for path in written)
    )
    assert json.loads(gzip.decompress(written[0].read_bytes()))["design"] == "source-han-sans"


def test_a_skipped_attempt_without_a_glyph_is_filed_by_its_subject() -> None:
    store = Store()
    description = table().first("仙")
    assert description is not None
    store.skip(reading.skipped(description, "no-face", "no font of the chain draws it"), "noto-sans-cjk-jp@2.004")
    ((name, content),) = store.files()
    assert name == "cuts/noto-sans-cjk-jp@2.004/04e.json.gz"
    assert problems("cuts", content) == [] and "glyph" not in content["skipped"][0]


def test_a_character_the_component_does_not_reach_is_not_attempted() -> None:
    found, drawings = pinned()
    assert list(survey.survey(found, drawings, "口", only="仙")) == []


def canonical(tree: str) -> str:
    """A tree as ids-input's survey wrote it (`{42}` and `&CDP-8958;`) as the structure level writes
    it, with the corpus's identifiers and the classes' canonical members: 亻 at the left is 人."""
    named, _ = descriptions.name_components(tree, descriptions.corpus_names())
    try:
        return structures.text(structures.Reader(classes.pinned()).canonical(structures.tree(ids.parse(named))))
    except ValueError:
        return tree


def reference(target: str) -> dict[str, tuple[str, int, list[tuple[int, float, float, float]]]]:
    out = {}
    for line in gzip.decompress((FIXTURES / f"{target}.tsv.gz").read_bytes()).decode("utf-8").splitlines()[1:]:
        char, tree, opened, instances = line.split("\t")
        rows = [tuple(float(part) for part in instance.split(":")) for instance in instances.split(" ")]
        out[char] = (tree, int(opened), sorted((int(d), fit, apart, away) for d, fit, apart, away in rows))
    return out


@pytest.mark.reproduction
@pytest.mark.parametrize("target", ["山", "口"])
def test_the_survey_of_ids_input_reproduces(target: str) -> None:
    """Every character of ids-input's survey has the same reading here: the same tree, written as
    a structure, the same depth and, for each instance, the same three scores. `expected.json`
    names the characters that differ, each for a reason `docs/reproduction.md` gives."""
    pinned()
    wanted = {char: (canonical(tree), opened, rows) for char, (tree, opened, rows) in reference(target).items()}
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))[target]
    mine = {}
    for outcome in survey.run(target):
        if outcome.readings is not None and (found := survey.instances(outcome.readings, target)):
            rows = sorted(
                (
                    sum(len(I.parse_path(step.split(":")[1])) for step in I.split_cut_id(cut["id"])[1]),
                    cut["evidence"]["fit"],
                    cut["checks"]["filled"]["value"],
                    cut["checks"]["skeleton"]["value"],
                )
                for cut in found
            )
            mine[outcome.char] = (canonical(outcome.readings[0]["tree"]), outcome.opened, rows)
    assert "".join(sorted(set(wanted) - set(mine))) == expected["lost"]
    assert "".join(sorted(set(mine) - set(wanted))) == expected["gained"]
    differ = []
    for char in sorted(set(mine) & set(wanted)):
        (tree, opened, rows), (other_tree, other_opened, other_rows) = mine[char], wanted[char]
        same = len(rows) == len(other_rows) and all(
            a[0] == b[0] and abs(a[1] - b[1]) < 0.0006 and a[2:] == b[2:]
            for a, b in zip(
                sorted(rows, key=lambda r: (r[0], r[2])), sorted(other_rows, key=lambda r: (r[0], r[2])), strict=True
            )
        )
        if not same or tree != other_tree or opened != other_opened:
            differ.append(char)
    assert "".join(differ) == expected["differ"]
    assert (len(mine), sum(len(rows) for _, _, rows in mine.values())) == tuple(expected["found"])
