"""The flat tables of a release: one row per cut, per drawn IDS, per structure of a character, per
skipped attempt, per class member, per component relation and per verdict, as tab-separated text.

A table starts with a line `# format=han-decompose/<name>-tsv@2.0`, with ` release=<version>` after
it in a release, then a line of column names. No field holds a tab or a line break; an absent value
is the empty string.
"""

import math
import re
from collections.abc import Iterable, Mapping
from decimal import Decimal

from . import identifiers as I
from .schema import Json

VERSION = "2.0"

COLUMNS = {
    "cuts": (
        "cut_id", "sig", "font", "design", "glyph", "char", "layer", "structure", "text", "tree", "path", "place",
        "depth", "whole", "class", "member", "style_basis", "style_tier", "contours", "grain", "box", "frame",
        "method", "tool", "fit", "margin", "agree", "reference", "filled", "skeleton", "calibrated", "division",
        "status",
    ),
    "drawn": (
        "font", "design", "glyph", "char", "structure", "text", "form", "tier", "stroke", "stroke_tier", "first",
    ),
    "structures": ("char", "structure", "text", "fonts", "designs", "forms"),
    "skipped": ("font", "glyph", "char", "layer", "structure", "text", "reason_code", "reason"),
    "classes": ("member", "target", "canonical", "place", "basis", "tier", "note"),
    "components": ("component", "kind", "text", "relation", "target", "basis", "tier"),
    "verdicts": ("cut_id", "sig", "verdict", "style", "note", "reviewer", "at", "release"),
}  # fmt: skip

Row = dict[str, str]

_RELEASE = re.compile(r"[0-9A-Za-z._+-]+")
_HEAD = re.compile(
    r"# format=han-decompose/(?P<name>[a-z]+)-tsv@(?P<major>[0-9]+)\.[0-9]+(?: release=(?P<release>[0-9A-Za-z._+-]+))?"
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def number(value: float | int) -> str:
    """A number as the tables write it: positional decimal with the fewest digits that read back to
    the same value, no exponent, no trailing zeros."""
    if isinstance(value, bool):
        raise TypeError("A truth value is not a number.")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError(f"{value} is not a finite number.")
    text = format(Decimal(repr(value)), "f")
    text = text.rstrip("0").rstrip(".") if "." in text else text
    return "0" if text == "-0" else text


def _numbers(values: Iterable[float | int] | None) -> str:
    return "" if values is None else " ".join(number(value) for value in values)


def _optional(value: float | int | str | None) -> str:
    return "" if value is None else value if isinstance(value, str) else number(value)


def _char(subject: str) -> str:
    """The subject as a character, when it is one."""
    return (I.written(subject) or "") if subject.startswith("u:") else ""


def _layer(steps: Iterable[str]) -> str:
    return "~".join(steps)


def cut_rows(cuts: Json) -> list[Row]:
    """A cut file's cuts as rows of the `cuts` table, in the file's order."""
    rows = []
    for reading in cuts["readings"]:
        _, selector = I.split_glyph_id(reading["glyph"])
        layer = reading["layer"]
        for cut in reading["cuts"]:
            evidence, checks, style = cut.get("evidence", {}), cut.get("checks", {}), cut.get("style", {})
            calibrated = cut.get("calibrated")
            rows.append({
                "cut_id": cut["id"],
                "sig": cut["sig"],
                "font": cuts["font"],
                "design": cuts["design"],
                "glyph": selector,
                "char": _char(reading["subject"]),
                "layer": _layer(layer),
                "structure": reading["structure"],
                "text": reading["text"],
                "tree": reading["tree"],
                "path": I.path_text(cut["path"]),
                "place": cut["place"],
                "depth": str(len(layer) + 1),
                "whole": "1" if not layer and len(cut["path"]) == 1 else "0",
                "class": cut["class"],
                "member": style.get("member", ""),
                "style_basis": style.get("basis", ""),
                "style_tier": style.get("tier", ""),
                "contours": _numbers(cut["contours"]),
                "grain": reading["method"]["grain"],
                "box": _numbers(cut["box"]),
                "frame": _numbers(cut.get("frame")),
                "method": reading["method"]["name"],
                "tool": reading["method"]["tool"],
                "fit": _optional(evidence.get("fit", evidence.get("match"))),
                "margin": _optional(evidence.get("margin")),
                "agree": _optional(evidence.get("agree")),
                "reference": _optional(evidence.get("reference")),
                "filled": _optional(checks.get("filled", {}).get("value")),
                "skeleton": _optional(checks.get("skeleton", {}).get("value")),
                "calibrated": "" if calibrated is None else calibrated or "0",
                "division": cut["division"],
                "status": cut["status"],
            })  # fmt: skip
    return rows


def drawn_rows(cuts: Json) -> list[Row]:
    """A cut file's drawn IDS as rows of the `drawn` table: one per glyph and structure."""
    rows = []
    for selector, entries in cuts["drawn"].items():
        char = I.selected(selector)
        for entry in entries:
            rows.append({
                "font": cuts["font"],
                "design": cuts["design"],
                "glyph": selector,
                "char": char or "",
                "structure": entry["structure"],
                "text": entry["text"],
                "form": entry["form"],
                "tier": entry["tier"],
                "stroke": entry.get("stroke", ""),
                "stroke_tier": entry.get("strokeTier", ""),
                "first": "1" if entry["first"] else "0",
            })  # fmt: skip
    return rows


def structure_rows(drawn: Iterable[Row]) -> list[Row]:
    """The `structures` table from the rows of `drawn`: per character and structure, the fonts and
    designs it fits and the distinct form levels it takes, each in the order first met."""
    found: dict[tuple[str, str], dict[str, list[str]]] = {}
    texts: dict[tuple[str, str], str] = {}
    for row in drawn:
        if not row["char"]:
            continue
        key = (row["char"], row["structure"])
        texts[key] = row["text"]
        held = found.setdefault(key, {"fonts": [], "designs": [], "forms": []})
        for name, value in (("fonts", row["font"]), ("designs", row["design"]), ("forms", row["form"])):
            if value not in held[name]:
                held[name].append(value)
    return [
        {
            "char": char,
            "structure": structure,
            "text": texts[char, structure],
            "fonts": " ".join(held["fonts"]),
            "designs": " ".join(held["designs"]),
            "forms": " ".join(held["forms"]),
        }
        for (char, structure), held in sorted(found.items(), key=lambda item: (ord(item[0][0][0]), item[0][1]))
    ]


def skipped_rows(cuts: Json) -> list[Row]:
    """A cut file's skipped attempts as rows of the `skipped` table, in the file's order."""
    return [
        {
            "font": cuts["font"],
            "glyph": I.split_glyph_id(row["glyph"])[1] if "glyph" in row else "",
            "char": _char(row["subject"]),
            "layer": _layer(row["layer"]),
            "structure": row.get("structure", ""),
            "text": row["text"],
            "reason_code": row["reason"]["code"],
            "reason": row["reason"]["text"],
        }
        for row in cuts["skipped"]
    ]


def write_table(name: str, rows: Iterable[Mapping[str, str]], release: str | None = None) -> str:
    """The table `name` as text: the format line, the column names, then the rows."""
    columns = COLUMNS[name]
    if release is not None and not _RELEASE.fullmatch(release):
        raise ValueError(f"{release!r} is not a release name.")
    head = f"# format=han-decompose/{name}-tsv@{VERSION}" + (f" release={release}" if release else "")
    lines = [head, "\t".join(columns)]
    for row in rows:
        if set(row) != set(columns):
            raise ValueError(f"A row of {name} has the columns {sorted(row)}.")
        fields = [row[column] for column in columns]
        if any(_CONTROL.search(field) for field in fields):
            raise ValueError(f"A field of {name} holds a control character: {fields}.")
        lines.append("\t".join(fields))
    return "\n".join(lines) + "\n"


def read_table(text: str) -> tuple[str, str | None, list[Row]]:
    """A table read back: its name, its release if it names one, and its rows."""
    lines = text.split("\n")
    if lines[-1] != "":
        raise ValueError("A table ends with a line feed.")
    head = _HEAD.fullmatch(lines[0])
    if head is None or head["name"] not in COLUMNS or head["major"] != VERSION.split(".")[0]:
        raise ValueError(f"{lines[0]!r} does not name a table of format {VERSION.split('.')[0]}.")
    name = head["name"]
    columns = COLUMNS[name]
    if tuple(lines[1:2]) != ("\t".join(columns),):
        raise ValueError(f"The columns of {name} are {' '.join(columns)}.")
    rows = []
    for at, line in enumerate(lines[2:-1], start=3):
        fields = line.split("\t")
        if len(fields) != len(columns) or any(_CONTROL.search(field) for field in fields):
            raise ValueError(f"Line {at} of {name} does not hold {len(columns)} fields free of control characters.")
        rows.append(dict(zip(columns, fields, strict=True)))
    return name, head["release"], rows
