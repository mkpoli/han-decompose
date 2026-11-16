import re
from pathlib import Path

import pytest

from han_decompose import tsv
from han_decompose.schema import Json, problems, validate

GOLDEN = Path(__file__).parent / "golden"


def _golden_rows(cuts: Json) -> dict[str, list[tsv.Row]]:
    drawn = tsv.drawn_rows(cuts)
    return {
        "cuts": tsv.cut_rows(cuts),
        "drawn": drawn,
        "structures": tsv.structure_rows(drawn),
        "skipped": tsv.skipped_rows(cuts),
    }


def test_the_golden_tables_are_the_cut_file_flattened(cuts: Json) -> None:
    for name, rows in _golden_rows(cuts).items():
        assert tsv.write_table(name, rows) == (GOLDEN / f"{name}.tsv").read_text(encoding="utf-8")


def test_a_row_stands_alone(cuts: Json) -> None:
    row = tsv.cut_rows(cuts)[2]
    assert row["char"] == "崔" and row["class"] == "u:5C71" and row["design"] == "source-han-sans"
    assert (row["path"], row["place"], row["depth"], row["whole"]) == ("0", "T", "2", "0")
    assert row["layer"] == "9d9dea39-hand:1" and row["structure"] == "s.a674f7d6" and row["text"] == "⿱山隹"
    assert row["contours"] == "0 2" and row["box"] == "366 595.22 924.5 831.92"
    assert row["division"] == "hand" and row["member"] == ""
    first = tsv.cut_rows(cuts)[0]
    assert (first["depth"], first["whole"], first["layer"]) == ("1", "1", "")


def test_a_style_fills_its_columns(cuts: Json) -> None:
    cuts["readings"][0]["cuts"][0]["style"] = {"member": "u:4EBB", "basis": "kage", "likeness": 0.9, "tier": "source"}
    row = tsv.cut_rows(cuts)[0]
    assert (row["member"], row["style_basis"], row["style_tier"]) == ("u:4EBB", "kage", "source")


def test_evidence_and_checks_fill_their_columns(cuts: Json) -> None:
    cut = cuts["readings"][0]["cuts"][1]
    cut["evidence"] = {"fit": 0.9123, "margin": 0.2, "agree": 3, "reference": 0.5}
    cut["checks"] = {"filled": {"value": 0.31, "limit": 0.6081, "pass": True}}
    cut["calibrated"] = False
    row = tsv.cut_rows(cuts)[1]
    assert (row["fit"], row["margin"], row["agree"], row["reference"]) == ("0.9123", "0.2", "3", "0.5")
    assert (row["filled"], row["skeleton"], row["calibrated"]) == ("0.31", "", "0")
    cut["calibrated"] = "u:5C71"
    assert tsv.cut_rows(cuts)[1]["calibrated"] == "u:5C71"


def test_a_structure_lists_the_fonts_and_forms_it_fits(cuts: Json) -> None:
    (row,) = tsv.drawn_rows(cuts)
    other = {**row, "font": "plangothic-p1@2.9.5795", "design": "plangothic", "form": "⿰亻⿱山隹'"}
    (found,) = tsv.structure_rows([row, other, {**row, "glyph": "gid.1", "char": ""}])
    assert found["fonts"] == "noto-sans-cjk-jp@2.004 plangothic-p1@2.9.5795"
    assert found["designs"] == "source-han-sans plangothic" and found["forms"] == "⿰亻⿱山隹 ⿰亻⿱山隹'"


@pytest.mark.parametrize(
    "value, text",
    [
        (366.0, "366"),
        (0.6081, "0.6081"),
        (0.03125, "0.03125"),
        (1e-7, "0.0000001"),
        (-0.0, "0"),
        (12, "12"),
        (-78.14, "-78.14"),
    ],
)
def test_numbers(value: float, text: str) -> None:
    assert tsv.number(value) == text


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_a_number_is_finite(value: float) -> None:
    with pytest.raises(ValueError):
        tsv.number(value)


def test_a_table_reads_back(cuts: Json) -> None:
    for name, rows in _golden_rows(cuts).items():
        assert tsv.read_table(tsv.write_table(name, rows, release="v2.0.0")) == (name, "v2.0.0", rows)
        assert tsv.read_table(tsv.write_table(name, rows)) == (name, None, rows)


def test_verdicts_components_and_classes_are_rows_the_schema_knows() -> None:
    verdict = {
        "cut_id": "noto-sans-cjk-jp@2.004/U+50AC~9d9dea39-deal:1~a674f7d6-deal:0",
        "sig": "785ad39d",
        "verdict": "right",
        "style": "",
        "note": "",
        "reviewer": "",
        "at": "2026-11-15T00:00:00Z",
        "release": "",
    }
    relation = {
        "component": "aj1:1815",
        "kind": "adobe-japan1",
        "text": "",
        "relation": "glyph-of",
        "target": "u:5F62",
        "basis": "Adobe-Japan1 CID order",
        "tier": "derived",
    }
    member = {
        "member": "u:793B",
        "target": "u:793A",
        "canonical": "u:793A",
        "place": "L",
        "basis": "positional-form",
        "tier": "source",
        "note": "",
    }
    for kind, name, row in (
        ("verdict", "verdicts", verdict),
        ("component", "components", relation),
        ("class", "classes", member),
    ):
        _, _, rows = tsv.read_table(tsv.write_table(name, [row]))
        assert rows == [row]
        validate(kind, rows[0])
    validate("verdict", {**verdict, "verdict": "", "style": "u:793B"})
    assert problems("verdict", {**verdict, "verdict": "maybe"})
    assert problems("component", {**relation, "tier": "attested"})
    assert problems("component", {**relation, "kind": "character"}) == ["aj1:1815: its kind is adobe-japan1."]
    assert problems("component", {**relation, "text": "x"}) == ["aj1:1815: it is written ''."]
    assert problems("component", {**relation, "target": ""})
    validate("component", {**relation, "relation": "", "target": "", "basis": "", "tier": ""})
    validate("component", {**relation, "component": "x:X-00777", "kind": "ledger", "text": "&X-00777;"})
    assert problems("component", {**relation, "relation": "same"})
    assert problems("class", {**member, "place": "left"}) and problems("class", {**member, "tier": "guess"})
    assert problems("class", {**member, "basis": "editorial"}) == [
        "u:793B: an editorial row has the tier editorial and a note."
    ]
    validate("class", {**member, "place": "", "basis": "editorial", "tier": "editorial", "note": "reviewed 2026-11-16"})
    assert problems("class", {**member, "tier": "editorial"})
    assert problems("class", {**member, "target": "u:793B"})


@pytest.mark.parametrize(
    "text",
    [
        "cut_id\tsig\n",
        "# format=han-decompose/cuts-tsv@1.0\n" + "\t".join(tsv.COLUMNS["cuts"]) + "\n",
        "# format=han-decompose/verdicts-tsv@2.0\ncut_id\tsig\n",
        "# format=han-decompose/verdicts-tsv@2.0\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\na\tb\n",
        "# format=han-decompose/verdicts-tsv@2.0\n" + "\t".join(tsv.COLUMNS["verdicts"]),
        "# format=han-decompose/verdicts-tsv@2.0\n",
        "# format=verdicts@1\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\n",
        "# format=han-decompose/verdicts-tsv@2.0 release=v1 beta\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\n",
        "# format=han-decompose/verdicts-tsv@2.0\r\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\r\n",
        "# format=han-decompose/verdicts-tsv@2.0\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\n" + "\t" * 7 + "\r\n",
    ],
)
def test_a_malformed_table_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        tsv.read_table(text)


@pytest.mark.parametrize("text", ["two\tfields", "two\nlines", "carriage\rreturn"])
def test_a_field_holds_no_control_character(cuts: Json, text: str) -> None:
    rows = tsv.skipped_rows(cuts)
    rows[0]["reason"] = text
    with pytest.raises(ValueError):
        tsv.write_table("skipped", rows)


@pytest.mark.parametrize("release", ["v1 beta", "v1\n", ""])
def test_a_release_name_has_no_space(cuts: Json, release: str) -> None:
    if release:
        with pytest.raises(ValueError):
            tsv.write_table("skipped", tsv.skipped_rows(cuts), release=release)
    else:
        assert tsv.read_table(tsv.write_table("skipped", [], release=None))[1] is None


def test_the_format_text_lists_the_columns_in_order() -> None:
    text = (Path(__file__).parents[1] / "docs" / "format.md").read_text(encoding="utf-8")
    seen = set()
    for section in text.split("\n### 5.")[1:]:
        body = section.split("\n## ")[0]
        names = re.findall(r"`([a-z]+)(?:\.tsv(?:\.gz)?)?`", body.splitlines()[0])
        cells = [line.split("|")[1] for line in body.splitlines() if line.startswith("| `")]
        if cells:
            documented = {names[0]: tuple(re.findall(r"`([a-z_]+)`", " ".join(cells)))}
        else:
            documented = {}
            for paragraph in body.split("\n\n"):
                found = re.match(r"`([a-z]+)\.tsv", paragraph)
                if found:
                    listed = re.sub(r"\([^)]*\)", "", paragraph.replace("\n", " ").split(":", 1)[1])
                    documented[found[1]] = tuple(re.findall(r"`([a-z_]+)`", listed))
        for name, columns in documented.items():
            assert columns == tsv.COLUMNS[name], name
            seen.add(name)
    assert seen == set(tsv.COLUMNS)
