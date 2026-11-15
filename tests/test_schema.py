import copy
from collections.abc import Callable

import pytest

from han_decompose import identifiers as I
from han_decompose.schema import FormatError, Json, box, point_count, problems, schema, validate


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


def _reading(cuts: Json) -> Json:
    reading: Json = cuts["readings"][0]
    return reading


def _resign(cut: Json, **changes: object) -> None:
    cut.update(changes)
    cut["sig"] = I.sig(cut["component"], cut["contours"])


def _twice(cuts: Json) -> None:
    again = copy.deepcopy(_reading(cuts))
    again["method"] = {"name": "deal", "tool": "han-decompose", "grain": "piece"}
    cuts["readings"].append(again)


def _guided(cuts: Json) -> None:
    _reading(cuts)["method"]["guide"] = "kanjivg"


OUTLINE_FAULTS: list[tuple[str, Callable[[Json], None]]] = [
    ("format: 'han-decompose/outlines@1.0' was expected", lambda o: o.update(format="han-decompose/outlines@2.0")),
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
]

CUT_FAULTS: list[tuple[str, Callable[[Json], None]]] = [
    ("terms: 'notices' is a required property", lambda c: c["terms"].pop("notices")),
    ("status: 'fine' is not one of", lambda c: _reading(c)["cuts"][0].update(status="fine")),
    ("component: '亻' is not valid", lambda c: _reading(c)["cuts"][0].update(component="亻")),
    ("'licence' is a required property", lambda c: _reading(c)["cuts"][0].pop("licence")),
    ("code: 'unknown' is not one of", lambda c: c["skipped"][0]["reason"].update(code="unknown")),
    ("opened/0: 'ids' is a required property", lambda c: _reading(c)["opened"][0].pop("ids")),
    ("opened/0/path: [] should be non-empty", lambda c: _reading(c)["opened"][0].update(path=[])),
    ("text: 'two\\tfields' holds a control character", lambda c: c["skipped"][0]["reason"].update(text="two\tfields")),
    ("not of noto-sans-cjk-jp@2.004", lambda c: _reading(c).update(glyph="jigmo@20250912/U+50AC")),
    ("is not the subject's, u:5C71", lambda c: _reading(c).update(subject="u:5C71")),
    ("does not name ⿰亻隹 in babelstone", lambda c: _reading(c).update(ids="⿰亻隹")),
    ("does not name ⿲亻丨备 in chise", lambda c: c.update(source="chise")),
    ("babelstone.a674f7d6 does not name ⿱山佳", lambda c: _reading(c)["opened"][0].update(ids="⿱山佳")),
    ("read twice under babelstone.9d9dea39", _twice),
    ("identifier does not name", lambda c: _reading(c)["cuts"][0].update(path=[1])),
    ("u:5C71 is not the component written 亻", lambda c: _resign(_reading(c)["cuts"][0], component="u:5C71")),
    ("signature is not that of its component and contours", lambda c: _reading(c)["cuts"][0].update(contours=[9])),
    ("signature is not that of its component and contours", lambda c: _reading(c)["cuts"][0].update(sig="9fccad38")),
    ("not ascending", lambda c: _reading(c)["cuts"][0].update(contours=[10, 9])),
    ("differ from the file's terms", lambda c: _reading(c)["cuts"][0]["licence"].update(outline="CC0-1.0")),
    ("guide's licence does not follow", lambda c: _reading(c)["cuts"][0]["licence"].update(guide="CC-BY-SA-3.0")),
    ("guide's licence does not follow", _guided),
    ("the glyph has 11 contours", lambda c: _resign(_reading(c)["cuts"][0], contours=[9, 11])),
    ("~0: the box is [0, 0, 1, 1]", lambda c: _reading(c)["cuts"][0].update(box=[0, 0, 1, 1])),
    ("contours [0] are also at 1.0", lambda c: _resign(_reading(c)["cuts"][2], contours=[0, 1])),
    ("marked complete with contours unclaimed", lambda c: _reading(c)["cuts"].pop()),
    ("U+50AD: the outline file does not hold the glyph", lambda c: _retarget(c, "U+50AD", "u:50AD")),
    ("U+507A: the outline file does not hold the glyph", lambda c: c["skipped"][0].update(glyph=c["font"] + "/U+507A")),
]


def _retarget(cuts: Json, selector: str, subject: str) -> None:
    reading = _reading(cuts)
    reading.update(glyph=I.glyph_id(cuts["font"], selector), subject=subject)
    for cut in reading["cuts"]:
        cut["id"] = I.cut_id(reading["glyph"], reading["description"], cut["path"])


@pytest.mark.parametrize("expected, fault", OUTLINE_FAULTS)
def test_a_faulty_outline_file_is_refused(outlines: Json, expected: str, fault: Callable[[Json], None]) -> None:
    fault(outlines)
    assert any(expected in problem for problem in problems("outlines", outlines)), problems("outlines", outlines)


@pytest.mark.parametrize("expected, fault", CUT_FAULTS)
def test_a_faulty_cut_file_is_refused(outlines: Json, cuts: Json, expected: str, fault: Callable[[Json], None]) -> None:
    fault(cuts)
    assert any(expected in problem for problem in problems("cuts", cuts, outlines)), problems("cuts", cuts, outlines)


def test_an_inner_node_holds_what_its_children_hold(outlines: Json, cuts: Json) -> None:
    reading = _reading(cuts)
    inner = copy.deepcopy(reading["cuts"][1])
    inner.update(path=[1], place="R", text="崔", id=I.cut_id(reading["glyph"], reading["description"], [1]))
    _resign(inner, component="u:5D14", contours=[0, 1, 2, 3, 4, 5, 6, 7])
    inner["box"] = box(outlines["glyphs"]["U+50AC"]["contours"], inner["contours"])
    reading["cuts"].append(inner)
    assert any("lacks a contour its descendant at 1.1 holds" in problem for problem in problems("cuts", cuts, outlines))
    _resign(inner, contours=[0, 1, 2, 3, 4, 5, 6, 7, 8])
    inner["box"] = box(outlines["glyphs"]["U+50AC"]["contours"], inner["contours"])
    validate("cuts", cuts, outlines)


def test_a_guided_reading_carries_the_guide_licence(outlines: Json, cuts: Json) -> None:
    cuts["terms"]["guide"] = "CC-BY-SA-3.0"
    validate("cuts", cuts, outlines)
    _guided(cuts)
    for cut in _reading(cuts)["cuts"]:
        cut["licence"]["guide"] = "CC-BY-SA-3.0"
    validate("cuts", cuts, outlines)


def test_the_golden_files_have_no_other_problem(outlines: Json, cuts: Json) -> None:
    assert problems("outlines", outlines) == [] and problems("cuts", cuts, outlines) == []


def test_cuts_are_checked_against_the_outlines_of_their_font(outlines: Json, cuts: Json) -> None:
    outlines["font"] = "jigmo@20250912"
    with pytest.raises(FormatError, match="The outlines are of jigmo@20250912"):
        validate("cuts", cuts, outlines)


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
    }
    fonts = {"format": "han-decompose/fonts@1.0", "fonts": [font], "chains": {"serif": ["jigmo2@20250912"]}}
    validate("fonts", fonts)
    assert problems("fonts", {**fonts, "fonts": [{**font, "sha256": "5da3"}]})
    assert problems("fonts", {**fonts, "chains": {"serif": []}})
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
    validate("sources", {"format": "han-decompose/sources@1.0", "sources": [source]})
    assert problems("sources", {"format": "han-decompose/sources@1.0", "sources": [{**source, "role": "oracle"}]})
