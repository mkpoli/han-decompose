from pathlib import Path

import pytest

from han_decompose import descriptions, pins

IDS_TXT = (
    "﻿# Ideographic Description Sequences\r\n"
    "#\t{42}\ttop of 录 (F2D4 \uf2d4)\t彐\r\n"
    "#\t{5}\tleft of 叚 (F2A9 \uf2a9)\t？\r\n"
    "#\t{82}\ttop of 書 (F2E3 \uf2e3)\t⿱𦘒一\r\n"
    "#\t{63}\t\r\n"
    "U+4E03\t七\t^〾⿻一乚$(GHJKPV)\t^〾⿻一㇄$(T)\r\n"
    "U+50AC\t催\t^⿰亻崔$(GHTJKPV)\t*an earlier sequence\r\n"
    "U+570A\t圊\t^⿴囗青$(GH[S])\t^⿴囗靑$(JK)\t^⿴囗青$(T)\r\n"
    "U+5F54\t彔\t^⿱{42}氺$\r\n"
)


def test_babelstone_keeps_each_sequence_with_its_regions(tmp_path: Path) -> None:
    path = tmp_path / "IDS.TXT"
    path.write_bytes(IDS_TXT.encode("utf-8"))
    table = descriptions.babelstone(path)
    assert [(row.text, row.tags) for row in table.of("七")] == [("〾⿻一乚", "GHJKPV"), ("〾⿻一㇄", "T")]
    assert [(row.text, row.tags) for row in table.of("催")] == [("⿰亻崔", "GHTJKPV")]
    assert table.first("彔") == descriptions.Description("babelstone", "彔", "⿱{42}氺")
    assert table.first("催").id == "babelstone.9d9dea39"  # type: ignore[union-attr]
    assert table.first("山") is None and table.of("山") == []
    assert [(row.text, row.tags) for row in table.of("圊")] == [("⿴囗青", "GH[S] T"), ("⿴囗靑", "JK")]


def test_babelstone_numbered_components_come_from_note_6(tmp_path: Path) -> None:
    path = tmp_path / "IDS.TXT"
    path.write_bytes(IDS_TXT.encode("utf-8"))
    table = descriptions.babelstone(path)
    assert table.numbered["{42}"] == descriptions.Numbered("{42}", "top of 录", "\uf2d4", "彐")
    assert table.numbered["{5}"].written is None and table.numbered["{63}"].pua == ""
    assert table.glyph("{42}") == "彐" and table.glyph("山") == "山"
    assert table.glyph("{5}") is None and table.glyph("{82}") is None and table.glyph("⿱山隹") is None


def test_babelstone_refuses_a_line_it_cannot_read(tmp_path: Path) -> None:
    path = tmp_path / "IDS.TXT"
    path.write_text("U+50AC\t催\t⿰亻崔\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable sequence"):
        descriptions.babelstone(path)
    path.write_text("U+50AD\t催\t^⿰亻崔$\n", encoding="utf-8")
    with pytest.raises(ValueError, match="writes U\\+50AD"):
        descriptions.babelstone(path)
    for line in ("#\t{42}\ttop of 录\t彐\n", "#\t{42}\ttop of 录 (F2D5 \uf2d4)\t彐\n"):
        path.write_text(line, encoding="utf-8")
        with pytest.raises(ValueError, match="numbered component"):
            descriptions.babelstone(path)


def test_only_a_description_source_has_a_table() -> None:
    with pytest.raises(KeyError, match="adobe-japan1 is not a description source"):
        descriptions.table("adobe-japan1")


def test_chise_reads_the_third_field_and_apparent_descriptions(tmp_path: Path) -> None:
    first, second = tmp_path / "IDS-UCS-Basic.txt", tmp_path / "IDS-UCS-Ext-A.txt"
    lines = [
        ";; -*- coding: utf-8-mcs-er -*-",
        "U+4E0E\t与\t⿹&CDP-8BBF;一",
        "U+4E9A\t亚\t亚\t@apparent=⿱一业",
        "CDP-8958\t&CDP-8958;\t⿱丷一",
    ]
    first.write_text("\n".join(lines) + "\n", encoding="utf-8")
    second.write_text("U+3400\t㐀\t⿱卝一\nU-00020000\t𠀀\t𠀀\n", encoding="utf-8")
    table = descriptions.chise([second, first])
    assert [(row.text, row.tags) for row in table.of("亚")] == [("亚", None), ("⿱一业", "apparent")]
    assert table.first("与").tree().children[0].text == "&CDP-8BBF;"  # type: ignore[union-attr]
    assert list(table.rows) == ["与", "亚", "㐀", "𠀀"]


def test_zi_tools_splits_a_field_into_its_alternatives(tmp_path: Path) -> None:
    path = tmp_path / "ids_lv1.txt"
    path.write_text("冐\t⿱冃⺝(.);⿱冃冃(K)\n马\t⿹𢎘一\nab\t⿰亻山\n", encoding="utf-8")
    table = descriptions.zi_tools(path)
    assert [row.text for row in table.of("冐")] == ["⿱冃⺝(.)", "⿱冃冃(K)"]
    assert table.first("冐").tree().children[1].text == "⺝"  # type: ignore[union-attr]
    assert "ab" not in table.rows


def test_the_pinned_tables_read() -> None:
    try:
        tables = {source: descriptions.table(source) for source in descriptions.SOURCES}
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    assert len(tables["babelstone"].rows) == 97680 and len(tables["babelstone"].numbered) == 122
    assert tables["babelstone"].first("催").text == "⿰亻崔"  # type: ignore[union-attr]
    assert tables["chise"].first("与").text == "⿹&CDP-8BBF;一"  # type: ignore[union-attr]
    assert tables["zi-tools"].first("马").text == "⿹𢎘一"  # type: ignore[union-attr]
