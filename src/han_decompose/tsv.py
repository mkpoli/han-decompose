"""The flat tables of a release: one row per cut, per skipped attempt, per component relation and
per verdict, as tab-separated text.

A table starts with a line `# format=han-decompose/<name>-tsv@1.0`, with ` release=<version>` after
it in a release, then a line of column names. No field holds a tab or a line break; an absent value
is the empty string.
"""

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from . import identifiers as I
from .schema import Json

VERSION = "1.0"

COLUMNS = {
    "cuts": (
        "cut_id", "sig", "font", "glyph", "char", "source", "description", "ids", "tree", "path", "place",
        "level", "whole", "component", "text", "contours", "grain", "box", "frame", "method", "tool",
        "fit", "margin", "agree", "reference", "filled", "skeleton", "calibrated", "status",
        "licence_outline", "licence_description", "licence_guide",
    ),
    "skipped": ("font", "glyph", "char", "source", "description", "ids", "reason_code", "reason"),
    "components": ("component", "kind", "text", "relation", "target", "basis", "tier", "source"),
    "verdicts": ("cut_id", "sig", "verdict", "note", "reviewer", "at", "release"),
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


def level(path: Sequence[int], opened: Iterable[Sequence[int]]) -> int:
    """How many descriptions deep a node sits: 1 in the subject's own description, one more for
    each node above it that was opened into its component's description."""
    return 1 + sum(1 for node in opened if len(node) < len(path) and tuple(path[: len(node)]) == tuple(node))


def cut_rows(cuts: Json) -> list[Row]:
    """A cut file's cuts as rows of the `cuts` table, in the file's order."""
    rows = []
    for reading in cuts["readings"]:
        font, glyph = I.split_glyph_id(reading["glyph"])
        opened = [node["path"] for node in reading.get("opened", ())]
        for cut in reading["cuts"]:
            evidence, checks = cut.get("evidence", {}), cut.get("checks", {})
            calibrated = cut.get("calibrated")
            rows.append({
                "cut_id": cut["id"],
                "sig": cut["sig"],
                "font": font,
                "glyph": glyph,
                "char": _char(reading["subject"]),
                "source": cuts["source"],
                "description": reading["description"],
                "ids": reading["ids"],
                "tree": reading["tree"],
                "path": I.path_text(cut["path"]),
                "place": cut["place"],
                "level": str(level(cut["path"], opened)),
                "whole": "1" if len(cut["path"]) == 1 else "0",
                "component": cut["component"],
                "text": cut["text"],
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
                "status": cut["status"],
                "licence_outline": cut["licence"]["outline"],
                "licence_description": cut["licence"]["description"],
                "licence_guide": cut["licence"].get("guide", ""),
            })  # fmt: skip
    return rows


def skipped_rows(cuts: Json) -> list[Row]:
    """A cut file's skipped attempts as rows of the `skipped` table, in the file's order."""
    return [
        {
            "font": cuts["font"],
            "glyph": I.split_glyph_id(row["glyph"])[1] if "glyph" in row else "",
            "char": _char(row["subject"]),
            "source": cuts["source"],
            "description": row["description"],
            "ids": row["ids"],
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
