"""Every Han glyph of the GlyphWiki dump: its outline file and its `kage` readings under each
candidate structure of its character.

One block of 256 code points is one unit of output. A worker draws a run of blocks with one engine
process (the engine holds the dump, some 300 MB), writes each block's outline file and cut file as
the block ends, and then a marker with the block's counts, so that a run that stopped goes on from
the blocks without one.
"""

import json
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Any

from .. import descriptions
from .. import glyphwiki as gw
from .. import glyphwiki_outlines as O
from .. import identifiers as I
from ..descriptions import Table
from ..outlines import write_block
from ..pieces import Glyph
from ..schema import Json
from ..store import Store, dumps, write
from . import kage, reading

SOURCES = ("babelstone", "chise", "zi-tools")
#: The names no selector spells, which no file holds.
UNSPELLED = "unspelled.txt"
#: Chunks of blocks per worker: one engine start (about 4 s) per chunk.
CHUNKS = 16


@dataclass
class Counts:
    """What a run of blocks gave."""

    glyphs: int = 0
    readings: int = 0
    cuts: int = 0
    #: Glyphs with a reading, and glyphs of a character that has a candidate structure.
    divided: int = 0
    attempted: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    #: Names the engine did not draw, by reason, and names the format cannot spell as a selector.
    failed: dict[str, int] = field(default_factory=dict)
    unspelled: int = 0

    def add(self, other: "Counts") -> None:
        for name in ("glyphs", "readings", "cuts", "divided", "attempted", "unspelled"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        for name in ("skipped", "failed"):
            mine: dict[str, int] = getattr(self, name)
            for key, total in getattr(other, name).items():
                mine[key] = mine.get(key, 0) + total

    def summary(self) -> Json:
        return {
            **self.__dict__,
            "skipped": dict(sorted(self.skipped.items())),
            "failed": dict(sorted(self.failed.items())),
        }


def block_names(names: Sequence[str]) -> tuple[dict[str, list[str]], list[str]]:
    """GlyphWiki names by the block of their file, in the order they are written, and the
    names that have no selector."""
    chosen: list[tuple[str, str]] = []
    unspelled: list[str] = []
    for name in names:
        selector = O.selector_of(name)
        if selector is None:
            unspelled.append(name)
        else:
            chosen.append((selector, name))
    chosen.sort(key=lambda pair: (I.order(pair[0]), pair[1]))
    out: dict[str, list[str]] = {}
    for selector, name in chosen:
        out.setdefault(I.shard(selector), []).append(name)
    return out, unspelled


def chunks(blocks: dict[str, list[str]], parts: int) -> list[list[str]]:
    """Runs of neighbouring blocks that hold about as many names, `parts` of them at most."""
    total = sum(len(names) for names in blocks.values())
    out: list[list[str]] = [[]]
    held = 0
    for block, names in blocks.items():
        if held >= total * len(out) / parts and out[-1] and len(out) < parts:
            out.append([])
        out[-1].append(block)
        held += len(names)
    return out


class Cutting:
    """What the cutter does for each glyph a block writes."""

    def __init__(self, font: str, tables: Sequence[Table], drawings: dict[str, gw.Drawing], names: dict[str, str]):
        self.font, self.tables, self.drawings, self.names = font, tables, drawings, names
        self.store = Store()
        self.counts = Counts()

    def watch(self, selector: str, glyph: Glyph) -> None:
        name = self.names[selector]
        self.counts.glyphs += 1
        info = gw.name_info(name)
        if info is None:
            return
        outcome = kage.cut_glyph(self.font, selector, name, glyph, kage.Division(self.drawings[selector]), self.tables)
        self.counts.attempted += bool(kage.candidates(self.tables, chr(info.code_point)))
        for row in outcome.readings:
            self.store.reading(row)
            self.counts.readings += 1 if not row["layer"] else 0
            self.counts.cuts += len(row["cuts"])
        self.counts.divided += bool(outcome.readings)
        for row in outcome.skipped:
            self.skip(row)

    def skip(self, row: Json) -> None:
        self.store.skip(row, self.font)
        code = row["reason"]["code"]
        self.counts.skipped[code] = self.counts.skipped.get(code, 0) + 1

    def nothing(self, name: str) -> None:
        """A character whose glyph the engine draws with no ink: one skipped attempt per structure."""
        info = gw.name_info(name)
        assert info is not None
        for description in kage.candidates(self.tables, chr(info.code_point)):
            if description.structure[:1] in I.OPERATORS:
                self.skip(reading.skipped(description, "no-ink", f"GlyphWiki draws {name} with no ink"))


class Observed(O.Drawn):
    """GlyphWiki's drawings, with a call for each glyph the writer asks for."""

    def __init__(self, font: str, drawings: dict[str, gw.Drawing], observe: Callable[[str, Glyph], None]):
        super().__init__(font, drawings)
        self.observe = observe

    def glyph(self, selector: str) -> Glyph | None:
        found = super().glyph(selector)
        if found is not None:
            self.observe(selector, found)
        return found


def write_one(block: str, rows: list[Json], font_row: Json, tables: Sequence[Table], out: Path) -> Counts:
    """One block: the outline file, the cut file, and the marker."""
    font = font_row["id"]
    drawn: dict[str, gw.Drawing] = {}
    names: dict[str, str] = {}
    work = Cutting(font, tables, drawn, names)
    for row in rows:
        selector = O.selector_of(row["name"])
        assert selector is not None
        if "error" in row:
            reason = row["error"]["reason"]
            work.counts.failed[reason] = work.counts.failed.get(reason, 0) + 1
            if reason == "no-ink" and selector.startswith("U+"):
                work.nothing(row["name"])
            continue
        drawn[selector] = gw.parse_drawing(row)
        names[selector] = row["name"]
    # A block that is written again starts from nothing: the writer leaves a file it finds alone.
    (out / "outlines" / font / f"{block}.json.gz").unlink(missing_ok=True)
    result = write_block(Observed(font, drawn, work.watch), block, sorted(drawn, key=I.order), out, font_row)
    if result.failed:
        raise RuntimeError(f"{block}: {result.failed[:3]}")
    work.store.rows[font] = font_row
    work.store.write(out)
    marker = out / "blocks" / f"{block}.json"
    write(marker.with_suffix(".part"), dumps(work.counts.summary()))
    marker.with_suffix(".part").replace(marker)
    return work.counts


_STATE: dict[str, Any] = {}


def _open(dump: gw.Dump, sources: Sequence[str], cache: Path | None) -> None:
    _STATE["dump"] = dump
    _STATE["row"] = O.font_row(dump)
    _STATE["tables"] = [descriptions.table(source, cache) for source in sources]


def _work(job: tuple[list[tuple[str, list[str]]], str]) -> list[tuple[str, Counts]]:
    blocks, out = job
    names = [name for _, listed in blocks for name in listed]
    by_name = {name: block for block, listed in blocks for name in listed}
    done: list[tuple[str, Counts]] = []
    for block, rows in groupby(gw.draw_rows(names, _STATE["dump"]), key=lambda row: by_name[row["name"]]):
        done.append((block, write_one(block, list(rows), _STATE["row"], _STATE["tables"], Path(out))))
    return done


def run(
    dump: gw.Dump,
    out: Path,
    workers: int = 2,
    sources: Sequence[str] = SOURCES,
    cache: Path | None = None,
    only: Sequence[str] | None = None,
) -> Iterator[tuple[str, Counts]]:
    """Every block of the dump's Han glyphs, each written under `out`. A block with a marker is
    left as it is."""
    blocks, unspelled = block_names(list(gw.cjk_names(gw.read_names(dump.path))))
    out.mkdir(parents=True, exist_ok=True)
    (out / UNSPELLED).write_text("".join(f"{name}\n" for name in unspelled), encoding="utf-8")
    todo = {
        block: names
        for block, names in blocks.items()
        if (only is None or block in only) and not (out / "blocks" / f"{block}.json").exists()
    }
    jobs = [([(block, todo[block]) for block in run], str(out)) for run in chunks(todo, workers * CHUNKS) if run]
    with ProcessPoolExecutor(workers, initializer=_open, initargs=(dump, sources, cache)) as pool:
        for done in pool.map(_work, jobs, chunksize=1):
            yield from done


def totals(out: Path) -> Counts:
    """The counts of every block that has a marker under `out`."""
    total = Counts()
    for marker in sorted((out / "blocks").glob("*.json")):
        found = Counts()
        for key, value in json.loads(marker.read_text(encoding="utf-8")).items():
            setattr(found, key, value)
        total.add(found)
    names = out / UNSPELLED
    total.unspelled = len(names.read_text(encoding="utf-8").split()) if names.exists() else 0
    return total
