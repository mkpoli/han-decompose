"""Validation of data files: the JSON Schema, and the invariants a schema cannot state."""

import json
import re
from collections.abc import Iterator, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import identifiers as I

Json = dict[str, Any]

SCHEMA_FILE = "1/han-decompose.schema.json"

#: The definition each kind of file, or row of a table, is checked against.
KINDS = {
    "fonts": "fontsFile",
    "sources": "sourcesFile",
    "outlines": "outlineFile",
    "cuts": "cutFile",
    "verdict": "verdictRow",
    "component": "componentRow",
}

_COMMAND = re.compile(r"M|L|C|Q([0-9]+)(\*?)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

#: The kind a row of the components table states for each kind of reference.
COMPONENT_KINDS = {
    "u": "character",
    "bs": "babelstone",
    "chise": "chise",
    "aj1": "adobe-japan1",
    "zi": "zi-tools",
    "ids": "subtree",
}


class FormatError(ValueError):
    """A value that does not follow the format, with every problem found."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def schema_path() -> Path:
    """The schema file: the copy an installed package carries, or the checkout's `schema/`."""
    packaged = Path(__file__).with_name("_schema") / SCHEMA_FILE
    return packaged if packaged.exists() else Path(__file__).resolve().parents[2] / "schema" / SCHEMA_FILE


@cache
def schema() -> Json:
    out: Json = json.loads(schema_path().read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(out)
    return out


@cache
def _validator(kind: str) -> Draft202012Validator:
    return Draft202012Validator({**schema(), "$ref": f"#/$defs/{KINDS[kind]}"})


def _strings(value: object, at: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield at, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield at, key
            yield from _strings(item, f"{at}/{key}".lstrip("/"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{at}/{index}".lstrip("/"))


def schema_problems(kind: str, value: object) -> list[str]:
    """Where `value` departs from the schema of `kind`, each as `<location>: <message>`, and each
    string that holds a control character, which no string of the format does."""
    errors = sorted(_validator(kind).iter_errors(value), key=lambda error: [str(part) for part in error.absolute_path])
    out = ["/".join(str(part) for part in error.absolute_path) + f": {error.message}" for error in errors]
    return out + [f"{at}: {text!r} holds a control character." for at, text in _strings(value) if _CONTROL.search(text)]


def point_count(commands: str) -> int:
    """How many points a contour's pen commands take: one each for `M` and `L`, three for `C`, n for
    `Q<n>` and for `Q<n>*`."""
    return sum(int(match[1]) if match[1] else 3 if match[0] == "C" else 1 for match in _COMMAND.finditer(commands))


def box(contours: Sequence[Sequence[Any]], indices: Sequence[int]) -> list[float]:
    """The box of the contours at `indices`: the span of their points, in units."""
    xs = [x for index in indices for x in contours[index][1][0::2]]
    ys = [y for index in indices for y in contours[index][1][1::2]]
    return [min(xs) / 100, min(ys) / 100, max(xs) / 100, max(ys) / 100]


def outline_problems(outlines: Json) -> list[str]:
    """Where an outline file that passes the schema breaks the format's invariants."""
    out = []
    for name, glyph in outlines["glyphs"].items():
        contours = glyph["contours"]
        for index, (commands, flat) in enumerate(contours):
            if len(flat) != 2 * point_count(commands):
                out.append(f"{name}: contour {index} has {len(flat) // 2} points for {commands}.")
        pieces = glyph["pieces"]
        if sorted(index for piece in pieces for index in piece) != list(range(len(contours))):
            out.append(f"{name}: the pieces do not hold each of the {len(contours)} contours once.")
        if any(piece != sorted(piece) for piece in pieces) or pieces != sorted(pieces, key=lambda piece: piece[0]):
            out.append(f"{name}: the pieces are not in ascending order.")
        if glyph["box"] != box(contours, range(len(contours))):
            out.append(f"{name}: the box is {glyph['box']}, the points span {box(contours, range(len(contours)))}.")
    return out


def cut_problems(cuts: Json, outlines: Json | None = None) -> list[str]:
    """Where a cut file that passes the schema breaks the format's invariants; with the outline
    file of its font, also whether each glyph and contour it names exists and each box is true."""
    out = []
    font, source, terms = cuts["font"], cuts["source"], cuts["terms"]
    if outlines is not None and outlines["font"] != font:
        return [f"The outlines are of {outlines['font']}, the cuts of {font}."]
    read: set[tuple[str, str]] = set()
    for row in [*cuts["readings"], *cuts["skipped"]]:
        where = row.get("glyph") or row["subject"]
        if "glyph" in row:
            glyph_font, selector = I.split_glyph_id(row["glyph"])
            if glyph_font != font:
                out.append(f"{where}: the glyph is not of {font}.")
            if row["subject"].startswith("u:") and selector.startswith("U+") and row["subject"][2:] != selector[2:]:
                out.append(f"{where}: the glyph is not the subject's, {row['subject']}.")
            if outlines is not None and selector not in outlines["glyphs"]:
                out.append(f"{where}: the outline file does not hold the glyph.")
        if row["description"] != I.description_id(source, row["ids"]):
            out.append(f"{where}: {row['description']} does not name {row['ids']} in {source}.")
    for reading in cuts["readings"]:
        glyph = reading["glyph"]
        if (glyph, reading["description"]) in read:
            out.append(f"{glyph}: read twice under {reading['description']}.")
        read.add((glyph, reading["description"]))
        for node in reading.get("opened", ()):
            if node["description"] != I.description_id(node["description"].rpartition(".")[0], node["ids"]):
                out.append(f"{glyph}: {node['description']} does not name {node['ids']}.")
        guide = reading["method"].get("guide")
        drawn = None if outlines is None else outlines["glyphs"].get(I.split_glyph_id(glyph)[1])
        seen: dict[tuple[int, ...], set[int]] = {}
        for cut in reading["cuts"]:
            path, contours, licence = tuple(cut["path"]), cut["contours"], cut["licence"]
            if cut["id"] != I.cut_id(glyph, reading["description"], path):
                out.append(f"{cut['id']}: the identifier does not name its glyph, description and path.")
            if cut["component"] != I.component_of(cut["text"]):
                out.append(f"{cut['id']}: {cut['component']} is not the component written {cut['text']}.")
            if contours != sorted(contours):
                out.append(f"{cut['id']}: the contours are not ascending.")
            if cut["sig"] != I.sig(cut["component"], contours):
                out.append(f"{cut['id']}: the signature is not that of its component and contours.")
            if any(licence[key] != terms[key] for key in ("outline", "description")):
                out.append(f"{cut['id']}: the licences differ from the file's terms.")
            if ("guide" in licence) != (guide is not None) or licence.get("guide", terms.get("guide")) != terms.get(
                "guide"
            ):
                out.append(
                    f"{cut['id']}: the guide's licence does not follow the reading's guide and the file's terms."
                )
            if drawn is not None and contours[-1] >= len(drawn["contours"]):
                out.append(f"{cut['id']}: the glyph has {len(drawn['contours'])} contours.")
            elif drawn is not None and cut["box"] != box(drawn["contours"], contours):
                out.append(
                    f"{cut['id']}: the box is {cut['box']}, the contours span {box(drawn['contours'], contours)}."
                )
            if path in seen:
                out.append(f"{cut['id']}: the path is labelled twice.")
            mine = set(contours)
            for other, theirs in seen.items():
                if other == path[: len(other)]:
                    if not mine <= theirs:
                        out.append(f"{cut['id']}: holds a contour its ancestor at {I.path_text(other)} lacks.")
                elif path == other[: len(path)]:
                    if not theirs <= mine:
                        out.append(f"{cut['id']}: lacks a contour its descendant at {I.path_text(other)} holds.")
                elif mine & theirs:
                    out.append(f"{cut['id']}: contours {sorted(mine & theirs)} are also at {I.path_text(other)}.")
            seen[path] = mine
        if drawn is not None and reading["complete"]:
            claimed = set().union(*seen.values()) if seen else set()
            if claimed != set(range(len(drawn["contours"]))):
                out.append(f"{glyph}: marked complete with contours unclaimed.")
    return out


def component_problems(row: Json) -> list[str]:
    """Where a row of the components table that passes the schema contradicts itself."""
    out = []
    kind, _ = I.split_component(row["component"])
    if row["kind"] != COMPONENT_KINDS[kind]:
        out.append(f"{row['component']}: its kind is {COMPONENT_KINDS[kind]}.")
    if row["text"] != (I.written(row["component"]) or ""):
        out.append(f"{row['component']}: it is written {I.written(row['component']) or ''!r}.")
    if len({bool(row[key]) for key in ("relation", "target", "tier")}) != 1:
        out.append(f"{row['component']}: a relation has a target and a tier, and a row without one has neither.")
    return out


def problems(kind: str, value: object, outlines: Json | None = None) -> list[str]:
    """Every problem of `value` as a file or row of `kind`: the schema's, then the invariants'."""
    found = schema_problems(kind, value)
    if found or not isinstance(value, dict):
        return found
    if kind == "outlines":
        return outline_problems(value)
    if kind == "cuts":
        return cut_problems(value, outlines)
    if kind == "component":
        return component_problems(value)
    return []


def validate(kind: str, value: object, outlines: Json | None = None) -> None:
    """Raise `FormatError` unless `value` follows the format as a file or row of `kind`."""
    found = problems(kind, value, outlines)
    if found:
        raise FormatError(found)
