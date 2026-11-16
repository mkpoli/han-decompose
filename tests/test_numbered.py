import pytest

from han_decompose import descriptions, numbered, pins
from han_decompose.cutters import lift
from han_decompose.cutters.deal import Skipped
from han_decompose.descriptions import Numbered, Table
from han_decompose.pieces import Drawing
from han_decompose.schema import problems

from .fonts import pinned_chain, pinned_face


def test_a_numbered_component_is_the_character_at_its_private_use_code_point() -> None:
    table = Table("babelstone")
    table.numbered["&bsp:42;"] = Numbered("&bsp:42;", "top of 录", "", "彐")
    table.numbered["&bsp:63;"] = Numbered("&bsp:63;", "", "", None)
    table.numbered["&bsp:5;"] = Numbered("&bsp:5;", "left of 叚", "", None)
    found = numbered.rows(table)
    assert [(row["component"], row["relation"], row["target"]) for row in found] == [
        ("bsp:5", "equivalent", "u:F2A9"),
        ("bsp:42", "equivalent", "u:F2D4"),
        ("bsp:63", "", ""),
    ]
    assert [row["text"] for row in found] == ["&bsp:5;", "&bsp:42;", "&bsp:63;"]
    names = frozenset({"bsp:5", "bsp:42"})
    assert [row["component"] for row in numbered.rows(table, names)] == ["bsp:5", "bsp:42"]
    assert numbered.unnamed(table, names) == ["&bsp:63;"] and numbered.unnamed(table, None) == []
    assert found[0]["basis"] == (
        "IDS.TXT note 6 gives the component (left of 叚) this code point in the BabelStone Han PUA font; "
        "version 1.472 of the font draws it there"
    )
    assert all(problems("component", row) == [] and row["kind"] == "numbered" for row in found)


def pinned() -> Table:
    try:
        return descriptions.table("babelstone")
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")


def test_babelstone_han_pua_draws_every_numbered_component_it_gives_a_code_point() -> None:
    table = pinned()
    pinned_face(numbered.FONT)
    found = numbered.glyphs(table)
    assert len(found) == 121 and "&bsp:63;" not in found
    assert found["&bsp:42;"].font == numbered.FONT and found["&bsp:42;"].selector == "U+F2D4"
    assert all(problems("outlines", outline_file({glyph.selector: glyph.record()})) == [] for glyph in found.values())


def outline_file(glyphs: dict[str, object]) -> dict[str, object]:
    row = pins.font(numbered.FONT)
    head = {"format": "han-decompose/outlines@2.0", "font": numbered.FONT, "licence": row["licence"]}
    return {**head, "copyright": row["copyright"], "em": 1000, "q": 100, "glyphs": glyphs}


def test_a_numbered_component_is_lifted_and_held_against_its_private_use_glyph() -> None:
    table = pinned()
    drawings = [Drawing(face) for face in pinned_chain("source-han-sans", "plangothic").faces]
    references = lift.numbered(table, Drawing(pinned_face(numbered.FONT)))
    assert references["&bsp:50;"][0] == "babelstone-han-pua@1.472/U+F319"
    row = next(row for row in lift.registry()[0] if row["text"] == "&bsp:55;")
    outcome = lift.component(row, {descriptions.CORPUS: descriptions.table(descriptions.CORPUS)}, drawings, references)
    assert outcome.component == "bsp:55" and outcome.kind == "numbered" and outcome.form is not None
    assert outcome.form["basis"] == "reference"
    chosen = next(cut for found in outcome.readings for cut in found["cuts"] if cut["id"] == outcome.form["cut"])
    assert chosen["class"] == "bsp:55" and chosen["evidence"]["referenceGlyph"] == references["&bsp:55;"][0]
    assert chosen["checks"]["reference"]["value"] >= lift.REFERENCE and chosen["division"] == "machine"


def test_the_private_use_glyph_confirms_a_cut_and_does_not_overrule_the_hosts() -> None:
    table = pinned()
    drawings = [Drawing(face) for face in pinned_chain("source-han-sans", "plangothic").faces]
    references = lift.numbered(table, Drawing(pinned_face(numbered.FONT)))
    row = next(row for row in lift.registry()[0] if row["text"] == "&bsp:50;")
    # {50}: three hosts leave the same コ, which is unlike the thin Song-style glyph of the PUA font.
    outcome = lift.component(row, {descriptions.CORPUS: descriptions.table(descriptions.CORPUS)}, drawings, references)
    assert outcome.form is not None and outcome.form["basis"] == "agree"
    chosen = next(cut for found in outcome.readings for cut in found["cuts"] if cut["id"] == outcome.form["cut"])
    assert chosen["evidence"]["reference"] < lift.REFERENCE and chosen["status"] == "accepted"
    assert set(chosen["checks"]) == {"agree"} and chosen["checks"]["agree"]["pass"]
    lifts = []
    for recipe in lift.recipes(row, table):
        try:
            lifts.append(lift.lift(drawings, recipe))
        except Skipped:
            continue
    assert lift.settle(lifts, references["&bsp:50;"][1], decides=True)[0] is None


def test_outlines_of_the_private_use_font_say_how_they_were_changed() -> None:
    from han_decompose.store import Store

    pinned_face(numbered.FONT)
    store = Store()
    glyph = numbered.glyphs(pinned())["&bsp:42;"]
    store.glyph(glyph)
    ((name, content),) = store.files()
    assert name == "outlines/babelstone-han-pua@1.472/0f2.json.gz" and content["licence"] == "Arphic-1999"
    assert "scaled from 1024 to 1000 units per em" in content["notice"] and problems("outlines", content) == []
    assert "Every glyph this file holds" in content["notice"] and "manifest.json" in content["notice"]
    store.stroke(numbered.FONT, "U+F2D4", {"cut": f"{numbered.FONT}/U+F2D4~0a1c0fdb-lift:-", "strokes": []})
    strokes = dict(store.files())[f"strokes/{numbered.FONT}/0f2.json.gz"]
    assert strokes["notice"] == content["notice"]
