"""Cut one component out of every character whose description reaches it.

A description does not always name the component itself. 仙 is ⿰亻山 and names 山; 催 is ⿰亻崔, and
the 山 sits a level down, inside 崔. So a description is spelled out through the components that
reach the one looked for: a leaf whose own description reaches it is replaced by that description,
down to the bottom. Branches that reach none are left as they stand. 催's tree is then ⿰亻⿱山隹.

The fullest spelling out is tried first, then shallower ones: a component the font draws joined
to its neighbour cannot be opened, and the instance the character names outright should not be
lost with it. A character is read in the first font of the chain that draws it and gives a
reading; the other fonts of the chain supply components the first does not draw.
"""

from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .. import descriptions, gates
from .. import identifiers as I
from ..descriptions import Description, Table
from ..ids import Node, leaves, spelled
from ..outline import Chain
from ..pieces import Drawing
from ..schema import Json
from . import reading
from .deal import Skipped, count, read

#: How many components deep a description may be spelled out.
MAX_LEVELS = 8


def tree_of(table: Table, char: str) -> tuple[Description, Node] | None:
    """A character's first description as a tree; None where the table writes the character as
    itself, without an operator, or not at all, or the description does not read."""
    description = table.first(char)
    if description is None or len(char) != 1:
        return None
    try:
        root = description.tree()
    except ValueError:
        return None
    return None if root.leaf else (description, root)


def holders(table: Table, target: str) -> set[str]:
    """Every character the target reaches up into, however deep it sits. Each leaf of each
    description is an edge from the component to the character written with it, and one walk up
    from the target answers the whole table."""
    users: dict[str, list[str]] = {}
    for char in table.rows:
        found = tree_of(table, char)
        if found is None:
            continue
        for leaf in leaves(found[1]):
            glyph = table.glyph(leaf.text)
            if glyph and glyph != char:
                users.setdefault(glyph, []).append(char)
    out: set[str] = set()
    queue = [target]
    while queue:
        for char in users.get(queue.pop(), ()):
            if char not in out:
                out.add(char)
                queue.append(char)
    return out - {target}


def grown(node: Node, table: Table, holds: set[str], seen: frozenset[str], cap: int) -> Node:
    """A description spelled out through the components in `holds`, at most `cap` components deep.
    An opened node keeps its component's text, so its pieces are still recognised by the glyph a
    font draws for it."""
    if not node.leaf:
        return Node(node.text, node.operator, [grown(child, table, holds, seen, cap) for child in node.children])
    glyph = table.glyph(node.text)
    if glyph is None or len(seen) > cap or glyph not in holds or glyph in seen:
        return node
    found = tree_of(table, glyph)
    if found is None:
        return node
    inside = grown(found[1], table, holds, seen | {glyph}, cap)
    return Node(node.text, inside.operator, inside.children, opened=found[0].text)


def readings(description: Description, table: Table, holds: set[str], target: str) -> list[tuple[int, Node]]:
    """The trees to try for one character, the fullest spelling out first, down to the shallowest
    that still reaches the target."""
    offered: list[tuple[int, Node]] = []
    last = None
    for cap in range(MAX_LEVELS + 1):
        root = grown(description.tree(), table, holds, frozenset({description.subject}), cap)
        text = spelled(root)
        if text == last:
            break
        last = text
        if any(table.glyph(leaf.text) == target for leaf in leaves(root)):
            offered.append((cap, root))
    return offered[::-1]


@dataclass
class Outcome:
    """What the survey made of one character: its readings, or the reason there is none."""

    char: str
    readings: list[Json] | None = None
    skipped: Json | None = None
    #: How many components deep the reading was spelled out, and the deepest a tree went.
    opened: int = 0
    fullest: int = 0
    #: The outline records of the glyphs the reading or the skipped attempt names, by glyph id.
    glyphs: dict[str, Json] = field(default_factory=dict)


def instances(rows: Sequence[Json], target: str) -> list[Json]:
    """The cuts of the readings of a glyph that are the target and passed its checks."""
    return [
        cut
        for row in rows
        for cut in row["cuts"]
        if cut["class"] == I.component_of(target) and cut["status"] == "accepted"
    ]


def survey(
    table: Table,
    drawings: Sequence[Drawing],
    target: str,
    only: Sequence[str] | None = None,
    holds: set[str] | None = None,
) -> Iterator[Outcome]:
    """Every character whose description reaches `target`, in code point order, read or skipped;
    with `only`, those of them it names, in its order. `holds` is `holders(table, target)` where
    the caller has it already."""
    holds = holders(table, target) if holds is None else holds
    gate = gates.gate(table.glyph, target)
    for char in sorted(holds) if only is None else [char for char in dict.fromkeys(only) if char in holds]:
        description = table.first(char)
        assert description is not None
        selector = f"U+{ord(char):04X}"
        drawn = [drawing for drawing in drawings if drawing.glyph(selector) is not None]
        if not drawn:
            yield Outcome(char, skipped=reading.skipped(description, "no-face", "no font of the chain draws it"))
            continue
        try:
            offered = readings(description, table, holds, target)
        except ValueError as error:
            offered = []
            last: tuple[str, str] | None = reading.unreadable(error)
        else:
            last = None
        outcome = None
        for cap, root in offered:
            for drawing in drawn:
                glyph = drawing.glyph(selector)
                assert glyph is not None
                try:
                    others = [drawing, *(other for other in drawings if other is not drawing)]
                    rows = read(glyph, others, description, root, table.glyph, whole=False, gate=gate)
                except Skipped as reason:
                    last = (reason.code, f"{drawing.id}, {count(cap, 'component')} deep: {reason.text}")
                    continue
                except (ValueError, KeyError, RecursionError) as error:
                    last = (
                        reading.unreadable(error, f"{drawing.id}: ")
                        if isinstance(error, ValueError)
                        else (
                            "unreadable-description",
                            f"{drawing.id}: unreadable description: {error}",
                        )
                    )
                    continue
                outcome = Outcome(char, readings=rows, opened=cap, fullest=offered[0][0])
                outcome.glyphs[rows[0]["glyph"]] = glyph.record()
                break
            if outcome is not None:
                break
        if outcome is None:
            code, text = last or ("unreadable-description", f"no reading of the description reaches {target}")
            first = drawn[0].glyph(selector)
            assert first is not None
            glyph_id = I.glyph_id(drawn[0].id, selector)
            outcome = Outcome(
                char, skipped=reading.skipped(description, code, text, glyph_id if first.contours else None)
            )
            if first.contours:
                outcome.glyphs[glyph_id] = first.record()
        yield outcome


_STATE: dict[str, object] = {}


def _open(designs: Sequence[str], source: str, target: str, cache: Path | None) -> None:
    _STATE["drawings"] = [Drawing(face) for face in Chain.pinned(designs, cache).faces]
    _STATE["table"] = descriptions.table(source, cache)
    _STATE["holds"] = holders(descriptions.table(source, cache), target)


def _work(job: tuple[str, list[str]]) -> list[Outcome]:
    target, chars = job
    return list(survey(_STATE["table"], _STATE["drawings"], target, chars, _STATE["holds"]))  # type: ignore[arg-type]


def run(
    target: str,
    designs: Sequence[str] = ("source-han-sans", "plangothic"),
    source: str = "babelstone",
    workers: int = 4,
    cache: Path | None = None,
) -> Iterator[Outcome]:
    """The survey of one component over the fonts of pinned designs and a pinned table, on several processes, in code
    point order whatever their number."""
    chars = sorted(holders(descriptions.table(source, cache), target))
    jobs = [(target, chars[at : at + 40]) for at in range(0, len(chars), 40)]
    with ProcessPoolExecutor(workers, initializer=_open, initargs=(designs, source, target, cache)) as pool:
        for outcomes in pool.map(_work, jobs):
            yield from outcomes
