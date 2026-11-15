from collections.abc import Callable

import pytest

from han_decompose import identifiers as I


def test_fonts_and_glyphs() -> None:
    assert I.font_id("noto-sans-cjk-jp", "2.004") == "noto-sans-cjk-jp@2.004"
    assert I.selector("催") == "U+50AC"
    assert I.selector("葛\U000e0100") == "U+845B.E0100"
    assert I.selector("𠬶") == "U+20B36"
    assert I.gid_selector(1234) == "gid.1234"
    assert I.glyph_id("jigmo2@20250912", "U+20B36") == "jigmo2@20250912/U+20B36"
    assert I.split_glyph_id("babelstone-han-pua@1.472/gid.7") == ("babelstone-han-pua@1.472", "gid.7")
    assert I.selected("U+845B.E0100") == "葛\U000e0100"
    assert I.selected("gid.7") is None


@pytest.mark.parametrize(
    "selector, shard", [("U+50AC", "050"), ("U+20B36", "20b"), ("U+845B.E0100", "084"), ("gid.9", "gid")]
)
def test_shards(selector: str, shard: str) -> None:
    assert I.shard(selector) == shard


def test_a_description_is_named_by_its_text() -> None:
    assert I.description_id("babelstone", "⿰亻崔") == "babelstone.9d9dea39"
    assert I.description_id("chise", "⿰亻崔") == "chise.9d9dea39"
    assert I.description_id("zi-tools", "⿱山隹") == "zi-tools.a674f7d6"


@pytest.mark.parametrize(
    "text, reference",
    [
        ("山", "u:5C71"),
        ("葛\U000e0100", "u:845B.E0100"),
        ("{42}", "bs:42"),
        ("&CDP-8958;", "chise:CDP-8958"),
        ("&U-i001+20B36;", "chise:U-i001+20B36"),
        ("#(丿𠃊)", "zi:#(丿𠃊)"),
        ("⿱𰀪亻", "ids:⿱𰀪亻"),
    ],
)
def test_components_as_sources_write_them(text: str, reference: str) -> None:
    assert I.component_of(text) == reference
    assert I.written(reference) == text


def test_an_adobe_japan1_glyph_has_no_written_form() -> None:
    assert I.component("aj1", "1815") == "aj1:1815"
    assert I.written("aj1:1815") is None


def test_cuts() -> None:
    glyph = "noto-sans-cjk-jp@2.004/U+50AC"
    cut = I.cut_id(glyph, "babelstone.9d9dea39", [1, 0])
    assert cut == "noto-sans-cjk-jp@2.004/U+50AC~babelstone.9d9dea39~1.0"
    assert I.split_cut_id(cut) == (glyph, "babelstone.9d9dea39", (1, 0))
    assert I.cut_id(glyph, "babelstone.9d9dea39", []).endswith("~-")
    assert I.parse_path("-") == ()


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
        lambda: I.description_id("babelstone", ""),
        lambda: I.component("u", "5c71"),
        lambda: I.component("u", "50AC\n"),
        lambda: I.component("bs", "042"),
        lambda: I.component("ids", "山"),
        lambda: I.split_component("kanji:山"),
        lambda: I.component_of("{x}"),
        lambda: I.component_of("{042}"),
        lambda: I.component_of("⿰"),
        lambda: I.component_of("催促"),
        lambda: I.parse_path("1..0"),
        lambda: I.parse_path("01"),
        lambda: I.split_cut_id("noto-sans-cjk-jp@2.004/U+50AC~babelstone.9d9dea39"),
        lambda: I.sig("u:5C71", []),
        lambda: I.sig("山", [0]),
    ],
)
def test_malformed_identifiers_are_refused(call: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        call()
