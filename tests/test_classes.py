from pathlib import Path

import pytest

from han_decompose import classes, corpus, pins
from han_decompose import identifiers as I
from han_decompose.schema import problems

ROWS = [
    classes.Row("u:793B", "u:793A", "L", "positional-form", "source"),
    classes.Row("u:2BED", "u:793B", "", "radical-form", "source"),
    classes.Row("u:2BEC", "u:793A", "", "radical-form", "source"),
    classes.Row("u:6C35", "u:6C34", "L", "positional-form", "source"),
]


def test_a_member_resolves_through_its_rows_at_the_place_they_name() -> None:
    table = classes.Classes(ROWS)
    assert table.canonical("u:793B", "L") == "u:793A"
    assert table.canonical("u:793B", "R") == "u:793B" and table.canonical("u:793B") == "u:793B"
    assert table.canonical("u:2BED", "L") == "u:793A" and table.canonical("u:2BED", "R") == "u:793B"
    assert table.canonical("u:2BEC", "R") == "u:793A" and table.canonical("u:5C71", "L") == "u:5C71"
    assert table.members("u:793A", "L") == ["u:793A", "u:2BEC", "u:2BED", "u:793B"]
    assert table.members("u:793A", "R") == ["u:793A", "u:2BEC"]


def test_a_member_that_leads_to_two_canonical_members_or_back_to_itself_is_in_no_class() -> None:
    table = classes.Classes(
        [
            classes.Row("u:4E00", "u:4E8C", "", "editorial", "editorial", "n"),
            classes.Row("u:4E00", "u:4E09", "", "editorial", "editorial", "n"),
            classes.Row("u:4E0A", "u:4E0B", "", "editorial", "editorial", "n"),
            classes.Row("u:4E0B", "u:4E0A", "", "editorial", "editorial", "n"),
        ]
    )
    assert table.canonical("u:4E00") == "u:4E00" and table.canonical("u:4E0A") == "u:4E0A"
    assert table.table() == []
    assert len(table.problems()) == 3


def test_the_table_gives_each_row_where_it_leads_at_its_place() -> None:
    rows = classes.Classes(ROWS).table()
    assert [(row["member"], row["place"], row["canonical"]) for row in rows] == [
        ("u:2BEC", "", "u:793A"),
        ("u:2BED", "", "u:793B"),
        ("u:6C35", "L", "u:6C34"),
        ("u:793B", "L", "u:793A"),
    ]
    assert all(problems("class", row) == [] for row in rows)


def test_corpus_rows_are_read_as_references_and_a_place_no_operand_has_is_left_out() -> None:
    found = corpus.Corpus(
        frozenset(),
        (),
        (
            ("ucs:793B", "ucs:793A", "positional-form", "left", "source"),
            ("ucs:27607", "ucs:8863", "positional-form", "partial", "source"),
            ("ucs:2EAD", "ucs:793B", "radical-form", "", "source"),
        ),
    )
    assert classes.corpus_rows(found) == [
        classes.Row("u:793B", "u:793A", "L", "positional-form", "source"),
        classes.Row("u:2EAD", "u:793B", "", "radical-form", "source"),
    ]


def test_the_reviewed_rows_are_editorial_with_their_date_in_the_note(tmp_path: Path) -> None:
    path = tmp_path / "classes.tsv"
    path.write_text(
        "member\ttarget\tplace\tnote\treviewer\tat\nids:⿸⿹丅丿丨\tu:793A\t\t示 drawn\tx\t2026-11-16\n", "utf-8"
    )
    (row,) = classes.editorial_rows(path)
    assert (row.basis, row.tier, row.note) == ("editorial", "editorial", "示 drawn; 2026-11-16")
    assert classes.editorial_rows()[0].target == "u:793A"


def test_the_pinned_corpus_makes_one_class_table() -> None:
    try:
        table = classes.pinned()
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    assert len(table.rows) == 489 and table.problems() == [] and len(table.table()) == 489
    assert table.canonical(I.component("u", "793B"), "L") == "u:793A"
    assert table.canonical("u:2EAD", "L") == "u:793A" and table.canonical("ids:⿸⿹丅丿丨") == "u:793A"
    assert table.canonical("u:5C71", "L") == "u:5C71"
