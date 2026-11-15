"""Readings and cuts as the format writes them (`docs/format.md`, 4.4), built from what a cutter
found."""

from collections.abc import Sequence

from .. import __version__, pins
from .. import identifiers as I
from ..descriptions import Description
from ..ids import Node, spelled, walk
from ..pieces import Glyph
from ..schema import Json, box

TOOL = "han-decompose"

_PLACES = {"⿰": "LR", "⿱": "TB", "⿲": "LCR", "⿳": "TMB"}


def place(operator: str, index: int) -> str:
    """Where an operand stands in its parent: a letter in a row or a stack, else the operator and
    the operand's index."""
    return _PLACES[operator][index] if operator in _PLACES else f"{operator}{index}"


def number(value: float, digits: int) -> float | int:
    """A number with at most `digits` decimals, whole where it is whole."""
    rounded = round(float(value), digits)
    return int(rounded) if rounded == int(rounded) else rounded


def licence(font: str, source: str, guide: str | None = None) -> Json:
    """The licences a cut names: its font's, its description source's, and its guide's."""
    out = {"outline": pins.font(font)["licence"], "description": pins.source(source)["licence"]}
    if guide:
        out["guide"] = pins.source(guide)["licence"]
    return out


def frame(glyph: Glyph, groups: Sequence[Sequence[int]]) -> list[float]:
    """The box of a parent node's ink: every contour of the cuts under it."""
    return box(glyph.contours, sorted({index for group in groups for index in group}))


def subject_of(description: Description) -> str:
    """The component a description is of."""
    return I.component_of(description.subject)


def cut(
    glyph: Glyph,
    description: Description,
    root: Node,
    path: Sequence[int],
    node: Node,
    contours: Sequence[int],
    status: str = "accepted",
    **more: object,
) -> Json:
    """One cut: a node of the reading's tree with its contours."""
    indices = sorted(contours)
    component = I.component_of(node.text)
    parent = root
    for index in path[:-1]:
        parent = parent.children[index]
    out: Json = {
        "id": I.cut_id(I.glyph_id(glyph.font, glyph.selector), description.id, path),
        "sig": I.sig(component, indices),
        "path": list(path),
        "place": place(parent.operator or "", path[-1]) if path else "",
        "component": component,
        "text": node.text,
        "contours": indices,
        "box": box(glyph.contours, indices),
        "status": status,
        "licence": licence(glyph.font, description.source),
    }
    out.update({key: value for key, value in more.items() if value is not None})
    return out


def reading(
    glyph: Glyph,
    description: Description,
    root: Node,
    method: str,
    grain: str,
    cuts: list[Json],
    evidence: Json | None = None,
) -> Json:
    """One reading of a glyph under a description."""
    claimed = {index for row in cuts for index in row["contours"]}
    paths = {tuple(row["path"]) for row in cuts}
    leaves = [path for path, node in walk(root) if node.leaf]
    out: Json = {
        "glyph": I.glyph_id(glyph.font, glyph.selector),
        "subject": subject_of(description),
        "description": description.id,
        "ids": description.text,
        "tree": spelled(root),
        "method": {"name": method, "tool": TOOL, "version": __version__, "grain": grain},
        "complete": claimed == set(range(len(glyph.contours))) and all(path in paths for path in leaves),
        "cuts": sorted(cuts, key=lambda row: row["path"]),
    }
    if description.tags:
        out["tags"] = description.tags
    opened = [
        {
            "path": list(path),
            "component": I.component_of(node.text),
            "description": I.description_id(description.source, node.opened),
            "ids": node.opened,
        }
        for path, node in walk(root)
        if node.opened is not None
    ]
    if opened:
        out["opened"] = opened
    if evidence:
        out["evidence"] = evidence
    return out


def skipped(description: Description, code: str, text: str, glyph: str | None = None) -> Json:
    """An attempt that closed no reading."""
    out: Json = {
        "subject": subject_of(description),
        "description": description.id,
        "ids": description.text,
        "reason": {"code": code, "text": text},
    }
    if glyph:
        out["glyph"] = glyph
    if description.tags:
        out["tags"] = description.tags
    return out
