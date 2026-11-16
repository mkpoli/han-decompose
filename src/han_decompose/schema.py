"""Validation of data files: the JSON Schema, and the invariants a schema cannot state."""

import json
import re
from collections.abc import Iterator, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import identifiers as I
from .ids import parse, walk
from .resources import resource

Json = dict[str, Any]

SCHEMA_FILE = "2/han-decompose.schema.json"

#: The definition each kind of file, or row of a table, is checked against.
KINDS = {
    "fonts": "fontsFile",
    "sources": "sourcesFile",
    "outlines": "outlineFile",
    "strokes": "strokeFile",
    "cuts": "cutFile",
    "forms": "formsFile",
    "library": "libraryFile",
    "manifest": "manifestFile",
    "verdict": "verdictRow",
    "component": "componentRow",
    "class": "classRow",
}

_COMMAND = re.compile(r"M|L|C|Q([0-9]+)(\*?)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

#: The kind a row of the components table states for each kind of reference.
COMPONENT_KINDS = {
    "u": "character",
    "ids": "subtree",
    "x": "ledger",
    "aj1": "adobe-japan1",
}


class FormatError(ValueError):
    """A value that does not follow the format, with every problem found."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def schema_path() -> Path:
    """The schema file: the copy an installed package carries, or the checkout's `schema/`."""
    return resource("schema") / SCHEMA_FILE


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
        for stroke in glyph.get("strokes", ()):
            if stroke["contours"][-1] >= len(contours):
                out.append(f"{name}: a stroke names contour {stroke['contours'][-1]} of {len(contours)}.")
    return out


def _ancestor(path: tuple[int, ...], other: tuple[int, ...]) -> bool:
    return other != path and path[: len(other)] == other


def cut_problems(cuts: Json, outlines: Json | None = None) -> list[str]:
    """Where a cut file that passes the schema breaks the format's invariants; with the outline
    file of its font, also whether each glyph and contour it names exists and each box is true."""
    out = []
    font = cuts["font"]
    if outlines is not None and outlines["font"] != font:
        return [f"The outlines are of {outlines['font']}, the cuts of {font}."]
    for selector in cuts["drawn"]:
        if outlines is not None and selector not in outlines["glyphs"]:
            out.append(f"{selector}: the outline file does not hold the glyph.")
    for row in cuts["skipped"]:
        where = row.get("glyph") or row["subject"]
        if "glyph" in row:
            glyph_font, selector = I.split_glyph_id(row["glyph"])
            if glyph_font != font:
                out.append(f"{where}: the glyph is not of {font}.")
            if outlines is not None and selector not in outlines["glyphs"]:
                out.append(f"{where}: the outline file does not hold the glyph.")
        if row["structure"] != I.structure_id(row["text"]):
            out.append(f"{where}: {row['structure']} does not name {row['text']}.")
    seen_methods: set[tuple[str, tuple[str, ...], str, str]] = set()
    chosen: dict[tuple[str, tuple[str, ...], str], list[tuple[bool, bool]]] = {}
    held: dict[str, set[int]] = {}
    for reading in cuts["readings"]:
        for cut in reading["cuts"]:
            held[cut["id"]] = set(cut["contours"])
    for reading in cuts["readings"]:
        glyph, layer = reading["glyph"], tuple(reading["layer"])
        glyph_font, selector = I.split_glyph_id(glyph)
        if glyph_font != font:
            out.append(f"{glyph}: the glyph is not of {font}.")
        if outlines is not None and selector not in outlines["glyphs"]:
            out.append(f"{glyph}: the outline file does not hold the glyph.")
        if not layer and reading["subject"].startswith("u:") and selector.startswith("U+"):
            if reading["subject"][2:] != selector[2:]:
                out.append(f"{glyph}: the glyph is not the subject's, {reading['subject']}.")
        if reading["structure"] != I.structure_id(reading["text"]):
            out.append(f"{glyph}: {reading['structure']} does not name {reading['text']}.")
        method = reading["method"]["name"]
        key = (glyph, layer, reading["structure"])
        if (*key, method) in seen_methods:
            out.append(f"{glyph}: read twice under {reading['structure']} by {method}.")
        seen_methods.add((*key, method))
        good = all(cut["status"] in ("accepted", "reviewed-right") for cut in reading["cuts"]) and bool(reading["cuts"])
        chosen.setdefault(key, []).append((reading["chosen"], good))
        try:
            root = parse(reading["text"])
        except ValueError as error:
            out.append(f"{glyph}: the text does not read as a structure: {error}")
            continue
        nodes = {path: node for path, node in walk(root)}
        drawn = None if outlines is None else outlines["glyphs"].get(selector)
        universe: set[int] | None = None
        if layer:
            parent = held.get(I.cut_id(glyph, layer))
            if parent is None:
                out.append(f"{glyph}: no cut {I.cut_id(glyph, layer)} for its layer to divide.")
            universe = parent
        elif drawn is not None:
            universe = set(range(len(drawn["contours"])))
        seen: dict[tuple[int, ...], set[int]] = {}
        for cut in reading["cuts"]:
            path, contours = tuple(cut["path"]), cut["contours"]
            if cut["id"] != I.cut_id(glyph, [*layer, I.step(reading["text"], method, path)]):
                out.append(f"{cut['id']}: the identifier does not name its glyph, layers, structure, method and path.")
            if path not in nodes:
                out.append(f"{cut['id']}: the structure has no node at {I.path_text(path)}.")
            else:
                try:
                    expected = I.component_of(nodes[path].text)
                except ValueError:
                    expected = None
                if cut["class"] != expected:
                    out.append(f"{cut['id']}: {cut['class']} is not the component at {I.path_text(path)}, {expected}.")
            if contours != sorted(contours):
                out.append(f"{cut['id']}: the contours are not ascending.")
            if cut["sig"] != I.sig(cut["class"], contours):
                out.append(f"{cut['id']}: the signature is not that of its class and contours.")
            if universe is not None and not set(contours) <= universe:
                out.append(f"{cut['id']}: holds contours {sorted(set(contours) - universe)} its layer lacks.")
            elif drawn is not None and cut["box"] != box(drawn["contours"], contours):
                out.append(
                    f"{cut['id']}: the box is {cut['box']}, the contours span {box(drawn['contours'], contours)}."
                )
            if path in seen:
                out.append(f"{cut['id']}: the path is labelled twice.")
            mine = set(contours)
            for other, theirs in seen.items():
                if _ancestor(path, other):
                    if not mine <= theirs:
                        out.append(f"{cut['id']}: holds a contour its ancestor at {I.path_text(other)} lacks.")
                elif _ancestor(other, path):
                    if not theirs <= mine:
                        out.append(f"{cut['id']}: lacks a contour its descendant at {I.path_text(other)} holds.")
                elif mine & theirs:
                    out.append(f"{cut['id']}: contours {sorted(mine & theirs)} are also at {I.path_text(other)}.")
            seen[path] = mine
        if universe is not None and reading["complete"]:
            claimed = set().union(*seen.values()) if seen else set()
            if claimed != universe:
                out.append(f"{glyph}: marked complete with contours unclaimed.")
    for (glyph, _, structure), flags in chosen.items():
        picked = [good for is_chosen, good in flags if is_chosen]
        if len(picked) != (1 if any(good for _, good in flags) else 0) or not all(picked):
            out.append(f"{glyph}: exactly one accepted reading of {structure} is chosen, and none else.")
    return out


def component_problems(row: Json) -> list[str]:
    """Where a row of the components table that passes the schema contradicts itself."""
    out = []
    kind, _ = I.split_component(row["component"])
    if kind not in COMPONENT_KINDS:
        return [f"{row['component']}: a {kind} reference has no row of its own."]
    if row["kind"] != COMPONENT_KINDS[kind]:
        out.append(f"{row['component']}: its kind is {COMPONENT_KINDS[kind]}.")
    if row["text"] != (I.written(row["component"]) or ""):
        out.append(f"{row['component']}: it is written {I.written(row['component']) or ''!r}.")
    if len({bool(row[key]) for key in ("relation", "target", "tier")}) != 1:
        out.append(f"{row['component']}: a relation has a target and a tier, and a row without one has neither.")
    return out


def class_problems(row: Json) -> list[str]:
    """Where a row of the classes table that passes the schema contradicts itself."""
    out = []
    if row["member"] == row["target"]:
        out.append(f"{row['member']}: a member is not its own target.")
    if row["basis"] == "editorial" and (row["tier"] != "editorial" or not row["note"]):
        out.append(f"{row['member']}: an editorial row has the tier editorial and a note.")
    elif row["basis"] != "editorial" and row["tier"] == "editorial":
        out.append(f"{row['member']}: only an editorial row has the tier editorial.")
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
    if kind == "class":
        return class_problems(value)
    return []


def validate(kind: str, value: object, outlines: Json | None = None) -> None:
    """Raise `FormatError` unless `value` follows the format as a file or row of `kind`."""
    found = problems(kind, value, outlines)
    if found:
        raise FormatError(found)
