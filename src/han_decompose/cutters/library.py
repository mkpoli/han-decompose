"""Read every description of a table: each character's glyph dealt to the components of each
description the source gives it, and deeper where the components can be told apart.

A leaf of a description is itself a character with a description. Where its pieces can be dealt
to the operands of that description, the leaf is opened and its operands are cut too, level by
level; a leaf whose pieces cannot be dealt stays whole. 催 ⿰亻崔 is read as 亻 and 崔, then 崔 as
山 over 隹, so one glyph gives a cut of every component it can be divided into.

One block of 256 code points is one job. A job writes the outline and cut files of its block and
answers with counts, so a table of any size is read in bounded memory and a run that stops can go
on from the blocks it has not written.
"""

from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import descriptions, gates
from .. import identifiers as I
from ..descriptions import Description, Table
from ..ids import Node
from ..outline import Chain
from ..pieces import Drawing
from ..schema import Json
from ..store import Store, dumps, outline_head, write
from . import reading
from .deal import Skipped, read

#: How many components deep a leaf may be opened.
MAX_LEVELS = 6
#: How many values a font keeps per process before they are dropped and made again.
KEPT = 20000


def opener(table: Table) -> Any:
    """What a leaf opens into: its component's first description as a tree, unless the component
    is already being opened above it, the trail is at its length, or it has no description with
    an operator."""

    def run(node: Node, trail: Sequence[str]) -> Node | None:
        char = table.glyph(node.text)
        if char is None or char in trail or len(trail) > MAX_LEVELS:
            return None
        description = table.first(char)
        if description is None:
            return None
        try:
            inside = description.tree()
        except ValueError:
            return None
        return None if inside.leaf else Node(node.text, inside.operator, inside.children, opened=description.text)

    return run


@dataclass
class Counts:
    """What reading a set of characters gave."""

    readings: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    cuts: dict[str, int] = field(default_factory=dict)
    #: Components with a cut of each status.
    components: dict[str, set[str]] = field(default_factory=dict)
    #: Glyphs the checks compared with, to be written with the outlines.
    against: set[str] = field(default_factory=set)

    def add(self, other: "Counts") -> None:
        self.readings += other.readings
        for code, total in other.skipped.items():
            self.skipped[code] = self.skipped.get(code, 0) + total
        for status, total in other.cuts.items():
            self.cuts[status] = self.cuts.get(status, 0) + total
        for status, found in other.components.items():
            self.components.setdefault(status, set()).update(found)
        self.against |= other.against

    def summary(self) -> Json:
        return {
            "readings": self.readings,
            "skipped": dict(sorted(self.skipped.items())),
            "cuts": dict(sorted(self.cuts.items())),
            "components": {status: len(found) for status, found in sorted(self.components.items())},
        }


def one(description: Description, drawings: Sequence[Drawing], table: Table, store: Store, counts: Counts) -> None:
    """One description read on its subject's glyph, in the first font of the chain where it closes."""
    selector = f"U+{ord(description.subject):04X}"
    try:
        readable = True
        if description.tree().leaf:
            return
        last = ("no-face", "no font of the chain draws it")
    except ValueError as error:
        readable = False
        last = reading.unreadable(error)
    drawn = [drawing for drawing in drawings if drawing.glyph(selector) is not None]
    gate = gates.gate(table.glyph)
    opening = opener(table)
    for drawing in drawn if readable else []:
        glyph = drawing.glyph(selector)
        assert glyph is not None
        others = [drawing, *(other for other in drawings if other is not drawing)]
        try:
            rows = read(glyph, others, description, description.tree(), table.glyph, gate=gate, opener=opening)
        except Skipped as reason:
            last = (reason.code, f"{drawing.id}: {reason.text}")
            continue
        except (ValueError, RecursionError) as error:
            last = (
                reading.unreadable(error, f"{drawing.id}: ")
                if isinstance(error, ValueError)
                else ("unreadable-description", f"{drawing.id}: the description does not read: {error}")
            )
            continue
        store.glyph(glyph)
        counts.readings += 1
        for row in rows:
            store.reading(row)
            for cut in row["cuts"]:
                counts.cuts[cut["status"]] = counts.cuts.get(cut["status"], 0) + 1
                counts.components.setdefault(cut["status"], set()).add(cut["class"])
                counts.against.update(
                    check["against"] for check in cut.get("checks", {}).values() if "against" in check
                )
        return
    first = drawn[0].glyph(selector) if drawn else None
    has_ink = first is not None and bool(first.contours)
    glyph_id = I.glyph_id(drawn[0].id, selector) if has_ink else None
    if first is not None and has_ink:
        store.glyph(first)
    store.skip(reading.skipped(description, *last, glyph_id), drawn[0].id if has_ink else drawings[0].id)
    counts.skipped[last[0]] = counts.skipped.get(last[0], 0) + 1


def block_of(char: str) -> str:
    return I.shard(f"U+{ord(char):04X}")


_STATE: dict[str, Any] = {}


def _open(designs: Sequence[str], source: str, cache: Path | None) -> None:
    _STATE["drawings"] = [Drawing(face) for face in Chain.pinned(designs, cache).faces]
    _STATE["table"] = descriptions.table(source, cache)


def _work(job: tuple[str, list[str], str]) -> tuple[str, Counts]:
    block, chars, out = job
    store, counts = Store(), Counts()
    table: Table = _STATE["table"]
    for char in chars:
        for description in table.of(char):
            one(description, _STATE["drawings"], table, store, counts)
    store.write(Path(out))
    # What a font keeps per component (fingerprints, gate references) is bounded, so a process
    # that reads a whole table does not grow without end.
    for drawing in _STATE["drawings"]:
        if len(drawing.kept) > KEPT:
            drawing.kept.clear()
    # The marker says the block is done: it is written last, and whole or not at all.
    marker = Path(out) / "blocks" / f"{block}.json"
    partial = marker.with_suffix(".part")
    write(partial, dumps({**counts.summary(), "against": sorted(counts.against)}))
    partial.replace(marker)
    return block, counts


def run(
    designs: Sequence[str],
    source: str,
    out: Path,
    workers: int = 4,
    cache: Path | None = None,
    only: Sequence[str] | None = None,
) -> Iterator[tuple[str, Counts]]:
    """Every description of a source read in the fonts of pinned designs, block by block, each block's files written
    under `out`. A block whose marker is already there is left as it is. `only` names blocks."""
    table = descriptions.table(source, cache)
    blocks: dict[str, list[str]] = {}
    for char in sorted(table.rows):
        if len(char) == 1:
            blocks.setdefault(block_of(char), []).append(char)
    jobs = [
        (block, chars, str(out))
        for block, chars in blocks.items()
        if (only is None or block in only) and not (out / "blocks" / f"{block}.json").exists()
    ]
    # Blocks differ in cost by an order of magnitude; one per task keeps the processes even.
    with ProcessPoolExecutor(workers, initializer=_open, initargs=(designs, source, cache)) as pool:
        yield from pool.map(_work, jobs, chunksize=1)


def named(out: Path, designs: Sequence[str], cache: Path | None = None) -> int:
    """Add the outlines of the glyphs the checks compared with, where no reading named them:
    each goes into the outline file of its block. How many were added."""
    import gzip
    import json

    wanted: set[str] = set()
    for marker in sorted((out / "blocks").glob("*.json")):
        wanted.update(json.loads(marker.read_text(encoding="utf-8")).get("against", ()))
    drawings = {face.id: Drawing(face) for face in Chain.pinned(designs, cache).faces}
    added = 0
    files: dict[Path, Json] = {}
    for glyph_id in sorted(wanted):
        font, selector = I.split_glyph_id(glyph_id)
        path = out / "outlines" / font / f"{I.shard(selector)}.json.gz"
        if path not in files:
            files[path] = json.loads(gzip.decompress(path.read_bytes())) if path.exists() else outline_head(font)
        if selector not in files[path]["glyphs"]:
            glyph = drawings[font].glyph(selector)
            if glyph is not None and glyph.contours:
                files[path]["glyphs"][selector] = glyph.record()
                added += 1
    for path, content in files.items():
        write(path, dumps(content))
    return added
