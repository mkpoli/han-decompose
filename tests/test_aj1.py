from collections import Counter
from pathlib import Path

import pytest

from han_decompose import aj1, pins, tsv
from han_decompose.schema import problems


def line(cid: int, jis: str, cmap: str, sequence: str) -> str:
    return "\t".join([str(cid), jis, *["*"] * 15, cmap, cmap, sequence, "1,1,1"])


def test_a_cid_is_a_glyph_of_the_character_adobe_gives_it(tmp_path: Path) -> None:
    path = tmp_path / "aj17-kanji.txt"
    path.write_text(
        "# Adobe-Japan1-7 Kanji Datafile\n"
        + "\n".join([
            line(1815, "23-33", "U+5F62", "<U+5F62,U+E0100>"),
            line(14521, "*", "U+2F39:U+5F50", "<U+5F50,U+E0100>"),
            line(13763, "*", "*", "<U+5DE5,U+E0101>"),
            line(15391, "*", "U+2E95", "<U+5F50,U+E0101>"),
        ])
        + "\n# EOF\n",
        encoding="utf-8",
    )  # fmt: skip
    kanji = aj1.table(path)
    assert aj1.glyph_of(kanji[1815])[::2] == ("u:5F62", "jis")
    assert aj1.glyph_of(kanji[14521])[::2] == ("u:5F50", "code-point")
    assert aj1.glyph_of(kanji[13763])[::2] == ("u:5DE5", "sequence")
    assert aj1.glyph_of(kanji[15391]) == (
        "u:5F50",
        "aj17-kanji.txt field 18: UniJIS-UTF32-H maps U+2E95 to the CID; field 20: the variation sequence <U+5F50,U+E0101>",
        "code-point",
    )
    found = aj1.rows(["&AJ1-01815;"], kanji)
    assert [(row["component"], row["relation"], row["target"], row["source"]) for row in found] == [
        ("chise:AJ1-01815", "same", "aj1:1815", "chise"),
        ("aj1:1815", "glyph-of", "u:5F62", "adobe-japan1"),
    ]
    assert found[0]["text"] == "&AJ1-01815;" and found[1]["text"] == "" and "JIS X 0208 23-33" in found[1]["basis"]
    assert "maps U+5F62 to the CID" in found[1]["basis"] and "<U+5F62,U+E0100>" in found[1]["basis"]
    assert all(problems("component", row) == [] for row in found)
    with pytest.raises(ValueError, match="no CID 9"):
        aj1.rows(["&AJ1-00009;"], kanji)
    path.write_text("1\t2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="2 fields"):
        aj1.table(path)


def test_every_entity_of_the_registry_has_its_character() -> None:
    try:
        found = aj1.pinned()
        paths = pins.source_paths(pins.source("adobe-japan1"), fetch=False)
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    kanji = aj1.table(paths["aj17-kanji.txt"])
    names = aj1.entities()
    assert len(names) == 164 and len(found) == 328
    assert Counter(aj1.glyph_of(kanji[int(name[5:-1])])[2] for name in names) == {
        "jis": 118,
        "code-point": 45,
        "sequence": 1,
    }
    assert all(problems("component", row) == [] for row in found)
    by = {row["component"]: row["target"] for row in found if row["relation"] == "glyph-of"}
    assert (by["aj1:1815"], by["aj1:1829"], by["aj1:2014"]) == ("u:5F62", "u:7CFB", "u:8015")
    assert (by["aj1:13701"], by["aj1:16955"], by["aj1:13763"]) == ("u:65E3", "u:7075", "u:5DE5")
    assert all(len(target) in (6, 7) for target in by.values())
    text = tsv.write_table("components", found)
    assert tsv.read_table(text)[2] == found
