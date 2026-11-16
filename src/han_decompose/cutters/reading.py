"""Readings and cuts as the format writes them (`docs/format.md`, 4.3), built from what a cutter
found.

A cutter reads one description of a glyph as a tree, a leaf of which it may open into its
component's own description. The format keeps each opened node as a layer: the node is a cut of the
layer above, and the cuts of its own parts are a reading of their own, whose cut identifiers name
the step above.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .. import __version__
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


def frame(glyph: Glyph, groups: Sequence[Sequence[int]]) -> list[float]:
    """The box of a parent node's ink: every contour of the cuts under it."""
    return box(glyph.contours, sorted({index for group in groups for index in group}))


def subject_of(description: Description) -> str:
    """The component a description is of."""
    return I.component_of(description.subject)


@dataclass(frozen=True)
class Layer:
    """One layer of a tree: the steps from the glyph to it, its structure's text and its node."""

    steps: tuple[str, ...]
    text: str
    node: Node
    #: The path of the node from the root of the whole tree.
    at: tuple[int, ...]


def layers(description: Description, root: Node, method: str) -> list[Layer]:
    """The layers of a tree: the glyph's own, then one for each node that was opened, in the order
    the tree is walked."""
    found = [Layer((), description.structure, root, ())]

    def visit(layer: Layer, node: Node, path: tuple[int, ...]) -> None:
        for index, child in enumerate(node.children):
            at = (*path, index)
            if child.opened is not None:
                step = I.step(layer.text, method, at[len(layer.at) :])
                inner = Layer((*layer.steps, step), child.opened, child, at)
                found.append(inner)
                visit(inner, child, at)
            else:
                visit(layer, child, at)

    visit(found[0], root, ())
    return found


def cut(
    glyph: Glyph,
    description: Description,
    root: Node,
    path: Sequence[int],
    node: Node,
    contours: Sequence[int],
    status: str = "accepted",
    method: str = "deal",
    division: str = "machine",
    **more: object,
) -> Json:
    """One cut: a node of the tree with its contours. Its path is that of its layer."""
    indices = sorted(contours)
    component = I.component_of(node.text)
    layer = max(
        (
            one
            for one in layers(description, root, method)
            if tuple(path[: len(one.at)]) == one.at and (not one.at or len(one.at) < len(path))
        ),
        key=lambda one: len(one.at),
    )
    local = tuple(path[len(layer.at) :])
    parent = layer.node
    for index in local[:-1]:
        parent = parent.children[index]
    out: Json = {
        "id": I.cut_id(I.glyph_id(glyph.font, glyph.selector), [*layer.steps, I.step(layer.text, method, local)]),
        "sig": I.sig(component, indices),
        "path": list(local),
        "place": place(parent.operator or "", local[-1]) if local else "",
        "class": component,
        "contours": indices,
        "box": box(glyph.contours, indices),
        "division": division,
        "status": status,
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
) -> list[Json]:
    """The readings of a glyph under a description: the glyph's own, and one for each opened node
    that has cuts. `evidence` belongs to the glyph's own."""
    glyph_id = I.glyph_id(glyph.font, glyph.selector)
    by_layer: dict[tuple[str, ...], list[Json]] = {}
    for row in cuts:
        by_layer.setdefault(tuple(I.split_cut_id(row["id"])[1][:-1]), []).append(row)
    held = {row["id"]: row["contours"] for row in cuts}
    out = []
    for layer in layers(description, root, method):
        mine = by_layer.get(layer.steps)
        if mine is None:
            continue
        universe = (
            set(range(len(glyph.contours))) if not layer.steps else set(held.get(I.cut_id(glyph_id, layer.steps), ()))
        )
        paths = {tuple(row["path"]) for row in mine}
        inside = _leaves(layer.node)
        opened = [
            {
                "path": list(path),
                "member": I.component_of(node.text),
                "structure": I.structure_id(node.opened or ""),
                "text": node.opened,
            }
            for path, node in walk(layer.node)
            if path and node.opened is not None and not _below(layer.node, path)
        ]
        row_out: Json = {
            "glyph": glyph_id,
            "subject": subject_of(description) if not layer.steps else I.component_of(layer.node.text),
            "layer": list(layer.steps),
            "structure": I.structure_id(layer.text),
            "text": layer.text,
            "tree": spelled(layer.node),
            "method": {"name": method, "tool": TOOL, "version": __version__, "grain": grain},
            "complete": {index for row in mine for index in row["contours"]} == universe
            and all(path in paths for path in inside),
            "chosen": all(row["status"] in ("accepted", "reviewed-right") for row in mine),
            "cuts": sorted(mine, key=lambda row: row["path"]),
        }
        if opened:
            row_out["opened"] = opened
        if evidence and not layer.steps:
            row_out["evidence"] = evidence
        out.append(row_out)
    return out


def _leaves(node: Node) -> list[tuple[int, ...]]:
    """The paths of the leaves of a layer: a node opened into a layer of its own stands as one."""
    out = []
    for path, inner in walk(node):
        if path and (inner.leaf or inner.opened is not None) and not _below(node, path):
            out.append(path)
    return out


def _below(node: Node, path: Sequence[int]) -> bool:
    """Whether a node of a layer lies inside an opened node, which belongs to a layer below."""
    here = node
    for index in path[:-1]:
        here = here.children[index]
        if here.opened is not None:
            return True
    return False


def skipped(description: Description, code: str, text: str, glyph: str | None = None) -> Json:
    """An attempt that closed no reading."""
    out: Json = {
        "subject": subject_of(description),
        "layer": [],
        "structure": I.structure_id(description.structure),
        "text": description.structure,
        "reason": {"code": code, "text": text},
    }
    if glyph:
        out["glyph"] = glyph
    return out
