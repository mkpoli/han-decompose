from pathlib import Path

import pytest

from han_decompose import glyphwiki as gw

FIXTURES = Path(__file__).parent / "fixtures" / "glyphwiki"
DUMP = FIXTURES / "dump.txt"


def test_dump_is_read_as_name_to_data() -> None:
    glyphs = gw.read_dump(DUMP)
    assert len(glyphs) == 20
    assert glyphs["u793e-j"] == "99:0:0:0:0:180:200:u793b-01$99:0:0:64:0:197:200:u571f-j"
    assert "name" not in glyphs


@pytest.mark.parametrize(
    ("name", "code_point", "selector", "suffix"),
    [
        ("u793e", 0x793E, None, None),
        ("u793e-j", 0x793E, None, "j"),
        ("u793b-01", 0x793B, None, "01"),
        ("u20b36", 0x20B36, None, None),
        ("u845b-ue0100", 0x845B, 0xE0100, None),
        ("u845b-ue0101-var-001", 0x845B, 0xE0101, "var-001"),
        ("u6f22-ufe00", 0x6F22, 0xFE00, None),
        ("u4eba-var-002", 0x4EBA, None, "var-002"),
    ],
)
def test_names_map_to_characters(name: str, code_point: int, selector: int | None, suffix: str | None) -> None:
    info = gw.name_info(name)
    assert info == gw.NameInfo(code_point, selector, suffix)


@pytest.mark.parametrize("name", ["cdp-8bf9", "koseki-000010", "a77uyh_abcde", "uabc", "ud800", "u793e_x"])
def test_names_without_a_code_point_have_none(name: str) -> None:
    assert gw.name_info(name) is None


def test_selectors_are_spelled_as_in_format_2() -> None:
    assert gw.NameInfo(0x845B, 0xE0100).selector_spelling == "U+845B.E0100"
    assert gw.NameInfo(0x793E, None, "j").selector_spelling == "U+793E"


def test_cjk_filter_keeps_han_and_drops_the_rest() -> None:
    names = ["u793e-j", "u3042", "u20b36", "u845b-ue0100", "cdp-8bf9", "ufe00", "u2ff0"]
    assert list(gw.cjk_names(names)) == ["u793e-j", "u20b36", "u845b-ue0100"]


def test_社_resolves_to_the_placements_of_礻_and_土() -> None:
    (drawing,) = gw.draw(["u793e"], DUMP)
    assert isinstance(drawing, gw.Drawing)
    assert [p.glyph for p in drawing.leaves()] == ["u793b-01", "u571f-j"]
    assert drawing.alias == "u793e-j"
    left, earth = drawing.leaves()
    assert left.strokes == (0, 1, 2, 3, 4)
    assert earth.strokes == (5, 6, 7)
    assert set(left.contours).isdisjoint(earth.contours)


def test_strokes_are_grouped_and_contours_carry_their_ids() -> None:
    (drawing,) = gw.draw(["u793e"], DUMP)
    assert isinstance(drawing, gw.Drawing)
    assert [s.type for s in drawing.strokes] == [1, 1, 2, 1, 2, 1, 1, 1]
    covered = [c for s in drawing.strokes for c in s.contours]
    assert covered == list(range(len(drawing.contours)))
    for stroke_id, stroke in enumerate(drawing.strokes):
        assert all(drawing.contours[c].stroke == stroke_id for c in stroke.contours)
    assert drawing.contours[0].placements == (0, 1)
    assert drawing.contours[-1].placements == (0, 2)


def test_a_glyph_of_strokes_alone_has_no_placement() -> None:
    (drawing,) = gw.draw(["u793a-01"], DUMP)
    assert isinstance(drawing, gw.Drawing)
    assert drawing.placements == ()
    assert len(drawing.strokes) == 5


def test_failures_come_back_with_a_reason() -> None:
    results = list(gw.draw(["u793a", "nope"], DUMP, workers=2))
    assert {r.name: r.reason for r in results if isinstance(r, gw.Failure)} == {"u793a": "no-ink", "nope": "no-data"}


def test_related_is_ignored() -> None:
    # the dump gives u793e the related glyph u3013 (〓); no part of the result names it
    assert "u793e | u3013" in DUMP.read_text(encoding="utf-8").replace("  ", " ")
    (drawing,) = gw.draw(["u793e"], DUMP)
    assert isinstance(drawing, gw.Drawing)
    assert all(p.glyph != "u3013" for p in drawing.placements)
    assert gw.read_dump(DUMP)["u793e"] == "99:0:0:0:0:200:200:u793e-j"


def test_ivs_glyph_places_its_form_components() -> None:
    (drawing,) = gw.draw(["u845b-ue0100"], DUMP)
    assert isinstance(drawing, gw.Drawing)
    assert [p.glyph for p in drawing.leaves()] == ["u8279-03", "u66f7-var-002"]


def test_pinned_versions_are_found_in_the_data() -> None:
    assert gw.pinned_versions(gw.read_dump(DUMP)) == {"u458d-j@3"}


def test_a_pinned_version_is_read_from_the_versions_file() -> None:
    dump = gw.Dump(DUMP, gw.DUMP_URL, 0, "", "2026-11-15T17:01:31Z")
    assert dump.versions.name == "versions_used.txt"
    (without,) = gw.draw(["u235b3"], DUMP)
    assert isinstance(without, gw.Drawing)
    assert without.missing == ("u458d-j@3",)
    assert [p.glyph for p in without.leaves()] == ["u6728-01"]
    (with_versions,) = gw.draw(["u235b3"], dump)
    assert isinstance(with_versions, gw.Drawing)
    assert with_versions.missing == ()
    assert [p.glyph for p in with_versions.leaves()] == ["u6728-01", "u864d-05"]


def test_versions_are_extracted_from_the_all_versions_dump(tmp_path: Path) -> None:
    all_versions = tmp_path / "all.txt"
    all_versions.write_text(
        " name | related | data\n u458d-j\\@2 | | 1:0:0:1:1:2:2\n u458d-j\\@3 | | 99:0:0:0:0:200:200:u458d\n"
        " u458d\\@1 | | 1:0:0:3:3:4:4\n",
        encoding="utf-8",
    )
    out = tmp_path / "used.txt"
    assert gw.extract_versions(all_versions, gw.read_dump(DUMP), out) == 1
    assert gw.read_dump(out) == {"u458d-j@3": "99:0:0:0:0:200:200:u458d"}


def test_names_alone_match_the_full_read() -> None:
    assert sorted(gw.read_names(DUMP)) == sorted(gw.read_dump(DUMP))
