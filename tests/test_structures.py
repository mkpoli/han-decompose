import pytest

from han_decompose import classes, corpus, ids, pins, structures
from han_decompose import identifiers as I

NAMES = frozenset({"bsp:42"})
TABLE = classes.Classes(
    [
        classes.Row("u:793B", "u:793A", "L", "positional-form", "source"),
        classes.Row("u:4EBB", "u:4EBA", "L", "positional-form", "source"),
        classes.Row("u:6238", "u:6236", "", "unifiable-variant", "source"),
    ]
)


def read(description: str, named: dict[str, str] | None = None) -> str:
    found = structures.parsed(description, NAMES)
    assert found is not None
    return structures.text(structures.Reader(TABLE, named).canonical(found))


def test_a_component_is_written_as_its_classs_canonical_member_at_its_place() -> None:
    assert read("⿰礻土") == read("⿰示土") == "⿰示土"
    assert read("⿱礻土") == "⿱礻土"
    assert read("⿰亻木") == "⿰人木" and read("⿰戸木") == "⿰戶木"
    assert I.structure_id(read("⿰礻土")) == "s.0a1c0fdb"


def test_a_chain_flattens_and_a_spelled_part_is_the_character() -> None:
    assert read("⿱一⿱二三") == "⿳一二三"
    assert read("⿱⿱一二三") == "⿳一二三" and read("⿰一⿰二三") == "⿲一二三"
    assert read("⿱艹⿰亻匕", {"⿰人匕": "化"}) == "⿱艹化"
    assert read("⿰亻匕", {"⿰人匕": "化"}) == "⿰人匕"


def test_a_description_without_a_structure_of_its_own_is_left_out() -> None:
    for description in ("〾⿻一乚", "㇯鸟丶", "⿰亻？", "⿰示jss土.", "⿱&bsp:7;一", "山", "⿰亻", "⿰亻山⿰"):
        assert structures.parsed(description, NAMES) is None
    assert structures.parsed("⿱{42}氺", NAMES) is not None
    assert read("⿰山︀木") == "⿰山木" and read("⿱一[1:]二(.,J)") == "⿱一二"


def test_a_corpus_gives_each_character_its_distinct_structures_in_order() -> None:
    rows = (
        ("ucs:793E", "⿰礻土", None, "ready"),
        ("ucs:793E", "⿰示土", None, "ready"),
        ("ucs:793E", "⿰示土.", None, "ready"),
        ("ucs:5316", "⿰亻匕", None, "ready"),
        ("ucs:82B1", "⿱艹⿰亻匕", None, "ready"),
        ("ucs:82B1", "⿱艹化", None, "empty"),
        ("x:X-00001", "⿰一二", None, "ready"),
    )
    found = structures.build(corpus.Corpus(NAMES, rows, ()), TABLE)
    assert found.by_char == {"社": ["⿰示土"], "化": ["⿰人匕"], "花": ["⿱艹化"]}
    assert found.named == {"⿰示土": "社", "⿰人匕": "化", "⿱艹化": "花"} and found.rows == 4


def test_the_pinned_corpus_gives_社_one_structure_and_a_character_that_names_it() -> None:
    try:
        found = structures.pinned()
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    assert found.by_char["社"] == ["⿰示土"] and found.by_char["說"] == found.by_char["説"] == ["⿰言兌"]
    assert found.by_char["花"] == ["⿱艸化"] and found.by_char["催"] == ["⿰人崔"]
    assert ids.parse(found.by_char["花"][0]).children[1].text == "化"
    assert len(found.by_char) > 100000 and len({s for v in found.by_char.values() for s in v}) > 130000
