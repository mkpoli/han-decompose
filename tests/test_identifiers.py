from collections.abc import Callable

import pytest

from han_decompose import identifiers as I


def test_fonts_and_glyphs() -> None:
    assert I.font_id("noto-sans-cjk-jp", "2.004") == "noto-sans-cjk-jp@2.004"
    assert I.selector("催") == "U+50AC"
    assert I.selector("葛\U000e0100") == "U+845B.E0100"
    assert I.selector("𠬶") == "U+20B36"
    assert I.gid_selector(1234) == "gid.1234"
    assert I.glyph_id("plangothic-p2@2.9.5795", "U+20B36") == "plangothic-p2@2.9.5795/U+20B36"
    assert I.split_glyph_id("babelstone-han-pua@1.472/gid.7") == ("babelstone-han-pua@1.472", "gid.7")
    assert I.selected("U+845B.E0100") == "葛\U000e0100"
    assert I.selected("gid.7") is None


@pytest.mark.parametrize(
    "selector, shard",
    [
        ("U+50AC", "050"),
        ("U+20B36", "20b"),
        ("U+845B.E0100", "084"),
        ("gid.9", "gid"),
        ("name.u793e-j", "079"),
        ("name.u20b36-01", "20b"),
        ("name.cdp-8bf9", "name"),
        ("name.u5927_x", "name"),
        ("name.ud800-x", "name"),
    ],
)
def test_shards(selector: str, shard: str) -> None:
    assert I.shard(selector) == shard


def test_a_structure_is_named_by_its_text() -> None:
    assert I.structure_id("⿰亻崔") == "s.9d9dea39"
    assert I.structure_id("⿱山隹") == "s.a674f7d6"
    assert I.structure_id("⿰示土") == "s.0a1c0fdb"


@pytest.mark.parametrize(
    "text, reference",
    [
        ("山", "u:5C71"),
        ("葛\U000e0100", "u:845B.E0100"),
        ("&X-00777;", "x:X-00777"),
        ("&⿸⿹丅丿丨;", "ids:⿸⿹丅丿丨"),
        ("⿱𰀪亻", "ids:⿱𰀪亻"),
    ],
)
def test_components_as_structures_write_them(text: str, reference: str) -> None:
    assert I.component_of(text) == reference
    expected = text if text[0] != "⿱" else f"&{text};"
    assert I.written(reference) == expected


@pytest.mark.parametrize("text", ["{42}", "&CDP-8958;", "&U-i001+20B36;", "#(丿𠃊)"])
def test_a_component_no_ledger_names_has_no_reference(text: str) -> None:
    with pytest.raises(I.UnknownComponent):
        I.component_of(text)


def test_an_adobe_japan1_glyph_has_no_written_form() -> None:
    assert I.component("aj1", "1815") == "aj1:1815"
    assert I.written("aj1:1815") is None


def test_cuts() -> None:
    glyph = "noto-sans-cjk-jp@2.004/U+50AC"
    steps = [I.step("⿰亻崔", "deal", [1]), I.step("⿱山隹", "deal", [0])]
    assert steps == ["9d9dea39-deal:1", "a674f7d6-deal:0"]
    cut = I.cut_id(glyph, steps)
    assert cut == "noto-sans-cjk-jp@2.004/U+50AC~9d9dea39-deal:1~a674f7d6-deal:0"
    assert I.split_cut_id(cut) == (glyph, steps)
    assert I.cut_id(glyph, [I.step("⿰亻崔", "kage", [])]).endswith(":-")
    assert I.parse_path("-") == ()


def test_glyphs_are_selected_by_name() -> None:
    assert I.name_selector("u793e-j") == "name.u793e-j"
    assert I.glyph_id("glyphwiki@20261115", "name.u793e-j@3") == "glyphwiki@20261115/name.u793e-j@3"
    assert I.shard("name.u793e-j") == "079" and I.selected("name.u793e-j") is None
    assert I.order("U+50AC") < I.order("gid.0") < I.order("name.a")


def test_a_signature_names_the_component_and_the_contour_set() -> None:
    assert I.sig("u:5C71", [2, 0]) == I.sig("u:5C71", [0, 2]) == I.h8("u:5C71 0 2")
    assert I.sig("u:5C71", [0, 2]) != I.sig("u:5C71", [0, 20])
    assert I.sig("u:5C71", [0, 2]) != I.sig("u:51F5", [0, 2])


@pytest.mark.parametrize(
    "call",
    [
        lambda: I.font_id("Noto Sans", "2.004"),
        lambda: I.font_id("noto-sans-cjk", "2.004#0"),
        lambda: I.selector("催促"),
        lambda: I.selector("催A"),
        lambda: I.glyph_id("noto-sans-cjk-jp", "U+50AC"),
        lambda: I.shard("u+50ac"),
        lambda: I.shard("U+050AC"),
        lambda: I.shard("U+D800"),
        lambda: I.shard("U+110000"),
        lambda: I.shard("U+50AC.0041"),
        lambda: I.shard("gid.01"),
        lambda: I.split_glyph_id("noto-sans-cjk-jp@2.004/U+50AC\n"),
        lambda: I.structure_id(""),
        lambda: I.structure_id("山"),
        lambda: I.name_selector("U793E"),
        lambda: I.component("u", "5c71"),
        lambda: I.component("u", "50AC\n"),
        lambda: I.component("bs", "42"),
        lambda: I.component("x", "X-777"),
        lambda: I.component("ids", "山"),
        lambda: I.split_component("kanji:山"),
        lambda: I.component_of("⿰"),
        lambda: I.component_of("催促"),
        lambda: I.parse_path("1..0"),
        lambda: I.parse_path("01"),
        lambda: I.split_cut_id("noto-sans-cjk-jp@2.004/U+50AC"),
        lambda: I.split_cut_id("noto-sans-cjk-jp@2.004/U+50AC~babelstone.9d9dea39~0"),
        lambda: I.step("", "deal", []),
        lambda: I.sig("u:5C71", []),
        lambda: I.sig("山", [0]),
    ],
)
def test_malformed_identifiers_are_refused(call: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        call()
