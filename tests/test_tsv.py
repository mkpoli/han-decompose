import re
from pathlib import Path

import pytest

from han_decompose import tsv
from han_decompose.schema import Json, problems, validate

GOLDEN = Path(__file__).parent / "golden"


def test_the_golden_tables_are_the_cut_file_flattened(cuts: Json) -> None:
    for name, rows in (("cuts", tsv.cut_rows(cuts)), ("skipped", tsv.skipped_rows(cuts))):
        assert tsv.write_table(name, rows) == (GOLDEN / f"{name}.babelstone.tsv").read_text(encoding="utf-8")


def test_a_row_stands_alone(cuts: Json) -> None:
    row = tsv.cut_rows(cuts)[1]
    assert row["char"] == "催" and row["text"] == "山" and row["component"] == "u:5C71"
    assert (row["path"], row["place"], row["level"], row["whole"]) == ("1.0", "T", "2", "0")
    assert row["contours"] == "0 2" and row["box"] == "366 595.22 924.5 831.92"
    assert row["licence_outline"] == "OFL-1.1" and row["licence_guide"] == ""


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


def test_levels() -> None:
    assert tsv.level([0], [[1]]) == 1
    assert tsv.level([1], [[1]]) == 1
    assert tsv.level([1, 0], [[1]]) == 2
    assert tsv.level([1, 0, 2], [[1], [1, 0]]) == 3


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
    rows = tsv.cut_rows(cuts)
    assert tsv.read_table(tsv.write_table("cuts", rows, release="v0.1.0")) == ("cuts", "v0.1.0", rows)
    assert tsv.read_table(tsv.write_table("skipped", tsv.skipped_rows(cuts))) == (
        "skipped",
        None,
        tsv.skipped_rows(cuts),
    )


def test_verdicts_and_components_are_rows_the_schema_knows() -> None:
    verdict = {
        "cut_id": "noto-sans-cjk-jp@2.004/U+50AC~babelstone.9d9dea39~1.0",
        "sig": "545b9749",
        "verdict": "right",
        "note": "",
        "reviewer": "",
        "at": "2026-11-15T00:00:00Z",
        "release": "",
    }
    relation = {
        "component": "chise:AJ1-01815",
        "kind": "chise",
        "text": "&AJ1-01815;",
        "relation": "same",
        "target": "aj1:1815",
        "basis": "the entity's name",
        "tier": "source",
        "source": "chise",
    }
    for kind, name, row in (("verdict", "verdicts", verdict), ("component", "components", relation)):
        _, _, rows = tsv.read_table(tsv.write_table(name, [row]))
        assert rows == [row]
        validate(kind, rows[0])
    assert problems("verdict", {**verdict, "verdict": "maybe"})
    assert problems("component", {**relation, "tier": "attested"})
    assert problems("component", {**relation, "kind": "character"}) == ["chise:AJ1-01815: its kind is chise."]
    assert problems("component", {**relation, "text": "AJ1-01815"}) == ["chise:AJ1-01815: it is written '&AJ1-01815;'."]
    assert problems("component", {**relation, "target": ""})
    validate("component", {**relation, "relation": "", "target": "", "basis": "", "tier": "", "source": ""})


@pytest.mark.parametrize(
    "text",
    [
        "cut_id\tsig\n",
        "# format=han-decompose/cuts-tsv@2.0\n" + "\t".join(tsv.COLUMNS["cuts"]) + "\n",
        "# format=han-decompose/verdicts-tsv@1.0\ncut_id\tsig\n",
        "# format=han-decompose/verdicts-tsv@1.0\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\na\tb\n",
        "# format=han-decompose/verdicts-tsv@1.0\n" + "\t".join(tsv.COLUMNS["verdicts"]),
        "# format=han-decompose/verdicts-tsv@1.0\n",
        "# format=verdicts@1\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\n",
        "# format=han-decompose/verdicts-tsv@1.0 release=v1 beta\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\n",
        "# format=han-decompose/verdicts-tsv@1.0\r\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\r\n",
        "# format=han-decompose/verdicts-tsv@1.0\n" + "\t".join(tsv.COLUMNS["verdicts"]) + "\n" + "\t" * 6 + "\r\n",
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
    for section in text.split("\n### 5.")[1:]:
        name = re.match(r"[0-9] `([a-z]+)`", section)
        assert name is not None
        body = section.split("\n## ")[0]
        cells = [line.split("|")[1] for line in body.splitlines() if line.startswith("| `")]
        listed = cells or [next(line for line in body.splitlines()[1:] if line.startswith("`"))]
        assert tuple(re.findall(r"`([a-z_]+)`", " ".join(listed))) == tsv.COLUMNS[name[1]]
