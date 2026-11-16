import copy
from collections.abc import Callable

import pytest

from han_decompose import identifiers as I
from han_decompose.schema import FormatError, Json, point_count, problems, schema, validate

LAYER = "9d9dea39-hand:1"


def test_the_golden_files_follow_the_format(outlines: Json, cuts: Json) -> None:
    validate("outlines", outlines)
    validate("cuts", cuts, outlines)


def test_every_reference_in_the_schema_resolves() -> None:
    defs = schema()["$defs"]

    def references(node: object) -> list[str]:
        if isinstance(node, dict):
            return [v for k, v in node.items() if k == "$ref"] + [r for v in node.values() for r in references(v)]
        return [r for v in node for r in references(v)] if isinstance(node, list) else []

    assert {reference.removeprefix("#/$defs/") for reference in references(defs)} <= set(defs)


def test_point_counts() -> None:
    assert point_count("MLLL") == 4
    assert point_count("MLQ4Q4Q3") == 13
    assert point_count("Q3*") == 3
    assert point_count("MCCL") == 8


def _reading(cuts: Json, at: int = 0) -> Json:
    reading: Json = cuts["readings"][at]
    return reading


def _resign(cut: Json, **changes: object) -> None:
    cut.update(changes)
    cut["sig"] = I.sig(cut["class"], cut["contours"])


def _twice(cuts: Json) -> None:
    again = copy.deepcopy(_reading(cuts))
    again["chosen"] = False
    cuts["readings"].append(again)


def _another_chosen(cuts: Json) -> None:
    again = copy.deepcopy(_reading(cuts))
    again["method"] = {"name": "deal", "tool": "han-decompose", "grain": "piece"}
    cuts["readings"].append(again)


def _retarget(cuts: Json, selector: str, subject: str) -> None:
    for reading in cuts["readings"]:
        reading.update(glyph=I.glyph_id(cuts["font"], selector))
    _reading(cuts).update(subject=subject)


OUTLINE_FAULTS: list[tuple[str, Callable[[Json], None]]] = [
    ("format: 'han-decompose/outlines@2.0' was expected", lambda o: o.update(format="han-decompose/outlines@1.0")),
    ("q: 100 was expected", lambda o: o.update(q=4)),
    ("'u50AC' does not match", lambda o: o["glyphs"].update({"u50AC": o["glyphs"]["U+50AC"]})),
    ("'U+050AC' does not match", lambda o: o["glyphs"].update({"U+050AC": o["glyphs"]["U+50AC"]})),
    ("contours/0/0: 'LLLL' does not match", lambda o: o["glyphs"]["U+50AC"]["contours"][0].__setitem__(0, "LLLL")),
    ("contours/0/0: 'MQ3*' does not match", lambda o: o["glyphs"]["U+50AC"]["contours"][0].__setitem__(0, "MQ3*")),
    ("contours/0/1/0: 601.74 is not of type", lambda o: o["glyphs"]["U+50AC"]["contours"][0][1].__setitem__(0, 601.74)),
    ("contour 0 has 3 points", lambda o: o["glyphs"]["U+50AC"]["contours"][0][1].__delitem__(slice(0, 2))),
    ("pieces do not hold", lambda o: o["glyphs"]["U+50AC"]["pieces"].pop()),
    ("pieces do not hold", lambda o: o["glyphs"]["U+50AC"]["pieces"][0].append(9)),
    ("ascending order", lambda o: o["glyphs"]["U+50AC"]["pieces"].reverse()),
    ("U+50AC: the box is", lambda o: o["glyphs"]["U+50AC"]["box"].__setitem__(0, 0)),
    ("copyright: 'a\\nb' holds a control character", lambda o: o.update(copyright="a\nb")),
    ("'sources' was unexpected", lambda o: o.update(sources=[])),
    (
        "a stroke names contour 11 of 11",
        lambda o: o["glyphs"]["U+50AC"].update(strokes=[{"type": 2, "contours": [11]}]),
    ),
    ("strokes/0/type: 8 is greater", lambda o: o["glyphs"]["U+50AC"].update(strokes=[{"type": 8, "contours": [0]}])),
]

CUT_FAULTS: list[tuple[str, Callable[[Json], None]]] = [
    ("'design' is a required property", lambda c: c.pop("design")),
    ("'terms' was unexpected", lambda c: c.update(terms={})),
    ("status: 'fine' is not one of", lambda c: _reading(c)["cuts"][0].update(status="fine")),
    ("class: '亻' is not valid", lambda c: _reading(c)["cuts"][0].update(**{"class": "亻"})),
    ("class: 'bs:42' is not valid", lambda c: _reading(c)["cuts"][0].update(**{"class": "bs:42"})),
    ("'division' is a required property", lambda c: _reading(c)["cuts"][0].pop("division")),
    ("'licence' was unexpected", lambda c: _reading(c)["cuts"][0].update(licence={})),
    ("code: 'unknown' is not one of", lambda c: c["skipped"][0]["reason"].update(code="unknown")),
    ("opened/0: 'text' is a required property", lambda c: _reading(c)["opened"][0].pop("text")),
    ("opened/0/path: [] should be non-empty", lambda c: _reading(c)["opened"][0].update(path=[])),
    ("text: 'two\\tfields' holds a control character", lambda c: c["skipped"][0]["reason"].update(text="two\tfields")),
    (
        "basis: 'guess' is not one of",
        lambda c: _reading(c)["cuts"][0].update(style={"member": "u:4EBB", "basis": "guess", "tier": "machine"}),
    ),
    ("not of noto-sans-cjk-jp@2.004", lambda c: _reading(c).update(glyph="jigmo@20250912/U+50AC")),
    ("is not the subject's, u:5C71", lambda c: _reading(c).update(subject="u:5C71")),
    ("does not name ⿰亻隹", lambda c: _reading(c).update(text="⿰亻隹")),
    ("does not name ⿲亻丨备", lambda c: c["skipped"][0].update(text="⿲亻丨备备")),
    ("read twice under s.9d9dea39 by hand", _twice),
    ("identifier does not name", lambda c: _reading(c)["cuts"][0].update(path=[1])),
    ("u:5C71 is not the component at 0", lambda c: _resign(_reading(c)["cuts"][0], **{"class": "u:5C71"})),
    ("the structure has no node at 2", lambda c: _reading(c)["cuts"][0].update(path=[2])),
    ("signature is not that of its class and contours", lambda c: _reading(c)["cuts"][0].update(contours=[9])),
    ("signature is not that of its class and contours", lambda c: _reading(c)["cuts"][0].update(sig="9fccad38")),
    ("not ascending", lambda c: _reading(c)["cuts"][0].update(contours=[10, 9])),
    ("holds contours [11] its layer lacks", lambda c: _resign(_reading(c)["cuts"][0], contours=[9, 11])),
    ("~9d9dea39-hand:0: the box is [0, 0, 1, 1]", lambda c: _reading(c)["cuts"][0].update(box=[0, 0, 1, 1])),
    ("contours [9] are also at 0", lambda c: _resign(_reading(c)["cuts"][1], contours=[8, 9])),
    ("marked complete with contours unclaimed", lambda c: _reading(c, 1)["cuts"].pop()),
    ("marked complete with contours unclaimed", lambda c: _reading(c)["cuts"].pop(0)),
    (
        "holds contours [8] its layer lacks",
        lambda c: _resign(_reading(c)["cuts"][1], contours=[0, 1, 2, 3, 4, 5, 6, 7]),
    ),
    ("no cut ", lambda c: _reading(c, 1).update(layer=["9d9dea39-hand:5"])),
    ("exactly one accepted reading of s.9d9dea39 is chosen", lambda c: _reading(c).update(chosen=False)),
    (
        "exactly one accepted reading of s.9d9dea39 is chosen",
        _another_chosen,
    ),
    ("U+50AD: the outline file does not hold the glyph", lambda c: _retarget(c, "U+50AD", "u:50AD")),
    ("U+507A: the outline file does not hold the glyph", lambda c: c["skipped"][0].update(glyph=c["font"] + "/U+507A")),
    ("U+50AD: the outline file does not hold the glyph", lambda c: c["drawn"].update({"U+50AD": c["drawn"]["U+50AC"]})),
]


@pytest.mark.parametrize("expected, fault", OUTLINE_FAULTS)
def test_a_faulty_outline_file_is_refused(outlines: Json, expected: str, fault: Callable[[Json], None]) -> None:
    fault(outlines)
    assert any(expected in problem for problem in problems("outlines", outlines)), problems("outlines", outlines)


@pytest.mark.parametrize("expected, fault", CUT_FAULTS)
def test_a_faulty_cut_file_is_refused(outlines: Json, cuts: Json, expected: str, fault: Callable[[Json], None]) -> None:
    fault(cuts)
    assert any(expected in problem for problem in problems("cuts", cuts, outlines)), problems("cuts", cuts, outlines)


def test_an_opened_node_is_a_cut_of_the_layer_above(cuts: Json) -> None:
    assert _reading(cuts, 1)["layer"] == [LAYER]
    assert _reading(cuts)["cuts"][1]["id"].endswith("~" + LAYER)


def test_a_style_names_how_a_cut_is_drawn(outlines: Json, cuts: Json) -> None:
    _reading(cuts)["cuts"][0]["style"] = {"member": "u:4EBB", "basis": "match", "likeness": 0.9123, "tier": "machine"}
    validate("cuts", cuts, outlines)


def test_the_golden_files_have_no_other_problem(outlines: Json, cuts: Json) -> None:
    assert problems("outlines", outlines) == [] and problems("cuts", cuts, outlines) == []


def test_cuts_are_checked_against_the_outlines_of_their_font(outlines: Json, cuts: Json) -> None:
    outlines["font"] = "jigmo@20250912"
    with pytest.raises(FormatError, match="The outlines are of jigmo@20250912"):
        validate("cuts", cuts, outlines)


def test_glyphs_are_selected_by_code_point_index_or_name() -> None:
    for selector in ("U+50AC", "U+845B.E0100", "gid.1234", "name.u793e-j", "name.u793e@3"):
        validate("outlines", _empty({selector: _square()}))
    for selector in ("gid.01", "name.U793E", "name."):
        assert problems("outlines", _empty({selector: _square()}))


def _square() -> Json:
    return {
        "contours": [["MLLL", [0, 0, 0, 100, 100, 100, 100, 0]]],
        "pieces": [[0]],
        "box": [0, 0, 1, 1],
        "advance": 1000,
    }


def _empty(glyphs: Json) -> Json:
    return {
        "format": "han-decompose/outlines@2.0",
        "font": "glyphwiki@20261115",
        "licence": "LicenseRef-GlyphWiki",
        "copyright": "GlyphWiki",
        "em": 1000,
        "q": 100,
        "glyphs": glyphs,
    }


def test_stroke_files() -> None:
    file = {
        "format": "han-decompose/strokes@2.0",
        "font": "glyphwiki@20261115",
        "licence": "LicenseRef-GlyphWiki",
        "copyright": "GlyphWiki",
        "glyphs": {
            "name.u793e-j": [
                {
                    "cut": "glyphwiki@20261115/name.u793e-j~0a1c0fdb-kage:0",
                    "strokes": [{"type": "㇑", "method": "neck", "contours": [0, 1], "tier": "machine"}],
                    "outline": {"0": [["MLLL", [0, 0, 0, 100, 100, 100, 100, 0]]]},
                }
            ]
        },
    }
    validate("strokes", file)
    assert problems("strokes", {**file, "glyphs": {"name.u793e-j": [{"cut": "x", "strokes": []}]}})


def test_registry_files() -> None:
    font = {
        "id": "jigmo2@20250912",
        "name": "Jigmo2",
        "version": "20250912",
        "file": "Jigmo-20250912-Jigmo2.ttf",
        "url": "https://kamichikoichi.github.io/jigmo/Jigmo-20250912.zip",
        "sha256": "5da3582efe77e22073b86b3b86b556d7111148a76b957cfb53318a91da2efff0",
        "archive": {
            "sha256": "5744c7386d129475d87607ca66d043c8793c65448adeaedc921b6931890e5d0b",
            "member": "Jigmo2.ttf",
        },
        "upem": 1024,
        "licence": "CC0-1.0",
        "copyright": "No rights reserved.",
        "style": "serif",
        "design": "jigmo",
        "grain": "piece",
    }
    design = {"id": "jigmo", "name": "Jigmo", "style": "serif", "chain": ["jigmo2@20250912"], "members": []}
    fonts = {"format": "han-decompose/fonts@2.0", "fonts": [font], "designs": [design]}
    validate("fonts", fonts)
    assert problems("fonts", {**fonts, "fonts": [{**font, "sha256": "5da3"}]})
    assert problems("fonts", {**fonts, "designs": [{**design, "chain": []}]})
    assert problems("fonts", {**fonts, "fonts": [{**font, "grain": "stroke"}]})
    assert problems("fonts", {"format": "han-decompose/fonts@2.0", "fonts": [font], "chains": {}})
    source = {
        "id": "babelstone",
        "name": "BabelStone IDS",
        "role": "description",
        "url": "https://www.babelstone.co.uk/CJK/IDS.TXT",
        "pin": "File Date 2025-06-27",
        "retrieved": "2026-11-15",
        "licence": "LicenseRef-BabelStone-IDS",
        "attribution": "BabelStone IDS by Andrew West",
    }
    validate("sources", {"format": "han-decompose/sources@2.0", "sources": [source]})
    assert problems("sources", {"format": "han-decompose/sources@2.0", "sources": [{**source, "role": "oracle"}]})


def test_forms_libraries_and_the_manifest() -> None:
    cut = "noto-sans-cjk-jp@2.004/U+50AC~9d9dea39-hand:0"
    forms = {
        "format": "han-decompose/forms@2.0",
        "design": "source-han-sans",
        "forms": {"u:4EBB": {"u:4EBB": {"cut": cut, "sig": "933d670e", "basis": "kage", "hosts": 2}}},
    }
    validate("forms", forms)
    assert problems("forms", {**forms, "forms": {"u:4EBB": {"u:4EBB": {"cut": cut, "sig": "933d670e", "basis": "x"}}}})
    library = {
        "format": "han-decompose/library@2.0",
        "design": "source-han-sans",
        "library": {"u:4EBB": {"u:4EBB": {"L": [cut]}}},
    }
    validate("library", library)
    assert problems("library", {**library, "library": {"u:4EBB": {"u:4EBB": {"L": []}}}})
    manifest = {
        "format": "han-decompose/manifest@2.0",
        "release": "v2.0.0",
        "tool": {"name": "han-decompose", "version": "0.0.1"},
        "fonts": [{"id": "noto-sans-cjk-jp@2.004", "sha256": "0" * 64}],
        "counts": {
            "noto-sans-cjk-jp@2.004": {
                "readings": 1,
                "skipped": 0,
                "cuts": {"accepted": 3},
                "structures": 1,
                "classes": 3,
            }
        },
        "files": [{"path": "fonts.json", "bytes": 10, "sha256": "1" * 64}],
    }
    validate("manifest", manifest)
    assert problems("manifest", {**manifest, "counts": {"noto-sans-cjk-jp@2.004": {"readings": 1}}})
