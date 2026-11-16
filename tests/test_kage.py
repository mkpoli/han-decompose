from pathlib import Path

import pytest

from han_decompose import glyphwiki as gw
from han_decompose import glyphwiki_outlines as O
from han_decompose import identifiers as I
from han_decompose.cutters import kage
from han_decompose.descriptions import Table
from han_decompose.schema import Json, problems
from han_decompose.store import Store

FIXTURES = Path(__file__).parent / "fixtures" / "glyphwiki"
FONT = "glyphwiki@20261115"


@pytest.fixture(scope="module")
def dump(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dump") / "dump.txt"
    path.write_text((FIXTURES / "dump.txt").read_text() + (FIXTURES / "shapes.txt").read_text(), encoding="utf-8")
    return path


def table(*rows: tuple[str, str]) -> Table:
    out = Table("babelstone", names=frozenset())
    for char, text in rows:
        out.add(char, text)
    return out


def cut(dump: Path, name: str, *rows: tuple[str, str]) -> tuple[kage.Outcome, Store]:
    """A glyph read under the given descriptions, with the files the store would write."""
    (drawing,) = gw.draw([name], dump)
    assert isinstance(drawing, gw.Drawing)
    selector = O.selector_of(name)
    assert selector is not None
    glyph = O.glyph_of(FONT, selector, drawing)
    outcome = kage.cut_glyph(FONT, selector, name, glyph, kage.Division(drawing), [table(*rows)])
    store = Store({FONT: {**_row()}})
    store.record(FONT, selector, glyph.record())
    for row in outcome.readings:
        store.reading(row)
    for row in outcome.skipped:
        store.skip(row, FONT)
    return outcome, store


def _row() -> Json:
    return O.font_row(gw.Dump(FIXTURES / "dump.txt", gw.DUMP_URL, 1, "0" * 64, "2026-11-15T17:01:31Z"))


def valid(store: Store) -> None:
    files = dict(store.files())
    for path, content in files.items():
        if path.startswith("cuts/"):
            outlines = files[path.replace("cuts/", "outlines/")]
            assert problems("cuts", content, outlines) == [], path


def reasons(outcome: kage.Outcome) -> list[str]:
    return [row["reason"]["code"] for row in outcome.skipped]


def test_社_is_cut_where_glyphwiki_placed_礻_and_土(dump: Path) -> None:
    outcome, store = cut(dump, "u793e", ("社", "⿰礻土"))
    (row,) = outcome.readings
    assert (row["method"]["name"], row["method"]["grain"], row["complete"], row["tree"]) == (
        "kage",
        "contour",
        True,
        "⿰礻土",
    )
    left, earth = row["cuts"]
    assert left["contours"] == list(range(0, 8)) and earth["contours"] == list(range(8, 14))
    assert (left["class"], left["place"], left["division"], left["status"]) == ("u:793B", "L", "source", "accepted")
    assert left["style"] == {
        "member": "u:793B",
        "basis": "kage",
        "tier": "source",
        "glyph": f"{FONT}/name.u793b-01",
    }
    assert earth["style"]["glyph"] == f"{FONT}/name.u571f-j"
    valid(store)


def test_a_placed_glyph_that_is_not_the_operand_is_skipped(dump: Path) -> None:
    outcome, _ = cut(dump, "u793e", ("社", "⿰示土"))
    assert outcome.readings == [] and reasons(outcome) == ["unlike-division"]
    assert "示 is placed as u793b-01" in outcome.skipped[0]["reason"]["text"]


def test_a_glyph_drawn_from_strokes_alone_has_no_division(dump: Path) -> None:
    outcome, _ = cut(dump, "u793a-01", ("示", "⿱二小"))
    assert outcome.readings == [] and reasons(outcome) == ["no-division"]
    assert outcome.skipped[0]["glyph"] == f"{FONT}/name.u793a-01"


def test_a_stack_is_matched_by_the_ink_and_an_ivs_glyph_reads_for_its_sequence(dump: Path) -> None:
    outcome, store = cut(dump, "u845b-ue0100", ("葛", "⿱艹曷"))
    (row,) = outcome.readings
    assert row["glyph"] == f"{FONT}/U+845B.E0100" and row["subject"] == "u:845B.E0100"
    assert [(c["place"], c["class"]) for c in row["cuts"]] == [("T", "u:8279"), ("B", "u:66F7")]
    assert row["cuts"][1]["style"]["glyph"] == f"{FONT}/name.u66f7-var-002"
    valid(store)


def test_a_stack_that_lies_side_by_side_is_a_layout_mismatch(dump: Path) -> None:
    outcome, _ = cut(dump, "u845b-ue0100", ("葛", "⿰艹曷"))
    assert reasons(outcome) == ["layout-mismatch"]


def test_a_glyph_that_places_a_name_the_dump_lacks_says_so(dump: Path) -> None:
    outcome, _ = cut(dump, "u845b", ("葛", "⿱艹曷"))
    assert reasons(outcome) == ["unlike-division"] and "u66f7-j" in outcome.skipped[0]["reason"]["text"]


def test_an_enclosure_is_matched_by_containment(dump: Path) -> None:
    outcome, store = cut(dump, "u570b", ("國", "⿴囗或"))
    (row,) = outcome.readings
    assert [(c["place"], c["class"]) for c in row["cuts"]] == [("⿴0", "u:56D7"), ("⿴1", "u:6216")]
    valid(store)
    swapped, _ = cut(dump, "u570b", ("國", "⿴或囗"))
    assert reasons(swapped) == ["layout-mismatch"]


def test_a_placement_with_components_of_its_own_is_opened_as_a_layer(dump: Path) -> None:
    outcome, store = cut(dump, "u5001-j", ("倁", "⿰亻知"), ("知", "⿰矢口"))
    outer, inner = outcome.readings
    assert (outer["layer"], outer["tree"], outer["opened"][0]["text"]) == ([], "⿰亻⿰矢口", "⿰矢口")
    step = I.step("⿰亻知", "kage", [1])
    assert inner["layer"] == [step] and inner["subject"] == "u:77E5"
    assert [c["class"] for c in inner["cuts"]] == ["u:77E2", "u:53E3"]
    assert inner["cuts"][0]["id"] == f"{FONT}/name.u5001-j~{step}~{I.step('⿰矢口', 'kage', [0])}"
    assert outer["cuts"][1]["contours"] == sorted(c for cut_ in inner["cuts"] for c in cut_["contours"])
    valid(store)


def test_a_leaf_is_one_cut_where_none_of_its_descriptions_fits_what_is_placed(dump: Path) -> None:
    outcome, _ = cut(dump, "u5001-j", ("倁", "⿰亻知"), ("知", "⿱矢口"))
    (row,) = outcome.readings
    assert row["tree"] == "⿰亻知" and "opened" not in row


def test_components_placed_apart_are_grouped_where_the_structure_keeps_them_together(dump: Path) -> None:
    outcome, store = cut(dump, "u8b1d", ("謝", "⿰訁射"), ("射", "⿰身寸"))
    outer, inner = outcome.readings
    assert outer["tree"] == "⿰訁⿰身寸"
    group = outer["cuts"][1]
    assert group["class"] == "u:5C04" and "style" not in group
    assert [c["class"] for c in inner["cuts"]] == ["u:8EAB", "u:5BF8"]
    assert group["contours"] == sorted(c for cut_ in inner["cuts"] for c in cut_["contours"])
    valid(store)


def test_a_structure_with_more_operands_than_placements_is_skipped(dump: Path) -> None:
    outcome, _ = cut(dump, "u793e", ("社", "⿲礻土口"))
    assert reasons(outcome) == ["unlike-division"]
    assert "places 2 components" in outcome.skipped[0]["reason"]["text"]


def test_a_description_that_does_not_read_or_names_no_identifier_is_skipped(dump: Path) -> None:
    outcome, _ = cut(dump, "u793e", ("社", "⿰礻"), ("社", "⿰{42}土"))
    assert reasons(outcome) == ["unreadable-description", "unnamed-component"]


def test_a_glyph_with_one_placement_and_strokes_of_its_own_is_not_drawn_from_strokes_alone(dump: Path) -> None:
    outcome, _ = cut(dump, "u51f6", ("凶", "⿻凵㐅"))
    assert reasons(outcome) == ["unlike-division"]
    assert "places 1 component" in outcome.skipped[0]["reason"]["text"]


def test_an_overlay_is_matched_by_overlapping_ink(dump: Path) -> None:
    outcome, _ = cut(dump, "u570b", ("國", "⿻囗或"))
    assert [r["tree"] for r in outcome.readings] == ["⿻囗或"]
    left = gw.Placement(0, "u4e00", None, 0, (0, 0, 50, 50), (0, 0, 50, 50), (0,), (0,))
    right = gw.Placement(1, "u4e8c", None, 0, (150, 0, 200, 50), (150, 0, 200, 50), (1,), (1,))
    assert kage._lies("⿻", [kage.Unit((left,)), kage.Unit((right,))]) == "u4e00 and u4e8c do not overlap"


def test_an_operator_with_no_layout_to_check_is_a_layout_mismatch(dump: Path) -> None:
    (drawing,) = gw.draw(["u793e"], dump)
    assert isinstance(drawing, gw.Drawing)
    unit = kage.Unit((drawing.placements[1],))
    assert kage._lies("⿾", [unit]) == "⿾ has no layout to check"
