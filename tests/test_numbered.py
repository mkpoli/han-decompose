import pytest

from han_decompose import descriptions, numbered, pins
from han_decompose.cutters import lift
from han_decompose.descriptions import Numbered, Table
from han_decompose.pieces import Drawing
from han_decompose.schema import problems

from .fonts import pinned_chain, pinned_face


def test_a_numbered_component_is_the_character_at_its_private_use_code_point() -> None:
    table = Table("babelstone")
    table.numbered["{42}"] = Numbered("{42}", "top of 录", "", "彐")
    table.numbered["{63}"] = Numbered("{63}", "", "", None)
    table.numbered["{5}"] = Numbered("{5}", "left of 叚", "", None)
    found = numbered.rows(table)
    assert [(row["component"], row["relation"], row["target"]) for row in found] == [
        ("bs:5", "same", "u:F2A9"),
        ("bs:42", "same", "u:F2D4"),
        ("bs:63", "", ""),
    ]
    assert found[0]["basis"] == "IDS.TXT note 6: its code point in BabelStone Han PUA 1.472 (left of 叚)"
    assert all(problems("component", row) == [] and row["source"] == "babelstone" for row in found)


def pinned() -> Table:
    try:
        return descriptions.table("babelstone")
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")


def test_babelstone_han_pua_draws_every_numbered_component_it_gives_a_code_point() -> None:
    table = pinned()
    pinned_face(numbered.FONT)
    found = numbered.glyphs(table)
    assert len(found) == 121 and "{63}" not in found
    assert found["{42}"].font == numbered.FONT and found["{42}"].selector == "U+F2D4"
    assert all(problems("outlines", outline_file({glyph.selector: glyph.record()})) == [] for glyph in found.values())


def outline_file(glyphs: dict[str, object]) -> dict[str, object]:
    row = pins.font(numbered.FONT)
    head = {"format": "han-decompose/outlines@1.0", "font": numbered.FONT, "licence": row["licence"]}
    return {**head, "copyright": row["copyright"], "em": 1000, "q": 100, "glyphs": glyphs}


def test_a_numbered_component_is_lifted_and_held_against_its_private_use_glyph() -> None:
    table = pinned()
    drawings = [Drawing(face) for face in pinned_chain("sans").faces]
    references = lift.numbered(table, Drawing(pinned_face(numbered.FONT)))
    assert references["{50}"][0] == "babelstone-han-pua@1.472/U+F319"
    row = next(row for row in lift.registry() if row["text"] == "{55}")
    outcome = lift.component(row, {"babelstone": table}, drawings, references)
    assert outcome.component == "bs:55" and outcome.kind == "numbered" and outcome.form is not None
    assert outcome.form["basis"] == "reference"
    chosen = next(cut for found in outcome.readings for cut in found["cuts"] if cut["id"] == outcome.form["cut"])
    assert chosen["text"] == "{55}" and chosen["evidence"]["referenceGlyph"] == references["{55}"][0]
    assert chosen["checks"]["reference"]["value"] >= lift.REFERENCE and chosen["licence"]["description"].startswith(
        "LicenseRef"
    )
