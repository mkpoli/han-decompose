"""The outline files of a font: every glyph its cmap reaches, read at the font's pinned instance,
written in the blocks of `docs/format.md` (4) as outline files of format 2.

A block is written whole by one process, so the files do not depend on how many processes ran,
and a block whose file is there is left as it is.
"""

from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import identifiers as I
from .outline import Face
from .pieces import Drawing
from .schema import Json
from .store import compressed, dumps, outline_head


@dataclass
class Block:
    """What writing one block of one font gave."""

    font: str
    block: str
    #: Glyphs written, glyphs without ink left out, and glyphs that could not be read, with why.
    written: int = 0
    empty: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    #: Whether the file was already there.
    kept: bool = False


def blocks_of(selectors: Sequence[str]) -> dict[str, list[str]]:
    """Selectors by the block of their file, each block in the order glyphs are written."""
    out: dict[str, list[str]] = {}
    for selector in sorted(selectors, key=I.order):
        out.setdefault(I.shard(selector), []).append(selector)
    return out


def write_block(drawing: Drawing, block: str, selectors: Sequence[str], out: Path, row: Json | None = None) -> Block:
    """One block's outline file under `out`, unless it is there or no glyph of the block draws
    anything. A glyph that draws nothing has no record; a glyph that cannot be read is reported and
    left out."""
    font = drawing.id
    result = Block(font, block)
    path = out / "outlines" / font / f"{block}.json.gz"
    if path.exists():
        result.kept = True
        return result
    file = outline_head(font, row)
    for selector in selectors:
        try:
            glyph = drawing.glyph(selector)
            if glyph is None or not glyph.contours:
                result.empty += 1
                continue
            file["glyphs"][selector] = glyph.record()
        except Exception as error:  # a font's odd glyph is reported, never allowed to stop the rest
            result.failed.append((selector, f"{type(error).__name__}: {error}"))
    result.written = len(file["glyphs"])
    drawing.kept.clear()
    if not file["glyphs"]:
        return result
    partial = path.with_name(f".{path.name}.part")
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(compressed(dumps(file)))
    partial.replace(path)
    return result


def dump(drawing: Drawing, out: Path, row: Json | None = None, only: Sequence[str] | None = None) -> Iterator[Block]:
    """Every block of a font, one process, in the order of the code points."""
    for block, selectors in blocks_of(list(drawing.face.selectors())).items():
        if only is None or block in only:
            yield write_block(drawing, block, selectors, out, row)


_STATE: dict[str, Any] = {}


def _open(font: str, cache: Path | None) -> None:
    _STATE["drawing"] = Drawing(Face.pinned(font, cache))


def _work(job: tuple[str, list[str], str]) -> Block:
    block, selectors, out = job
    return write_block(_STATE["drawing"], block, selectors, Path(out))


def run(
    font: str, out: Path, workers: int = 4, cache: Path | None = None, only: Sequence[str] | None = None
) -> Iterator[Block]:
    """Every block of a pinned font on several processes, in the order of the code points whatever
    their number."""
    face = Face.pinned(font, cache)
    try:
        blocks = blocks_of(list(face.selectors()))
    finally:
        face.close()
    jobs = [(block, selectors, str(out)) for block, selectors in blocks.items() if only is None or block in only]
    with ProcessPoolExecutor(workers, initializer=_open, initargs=(font, cache)) as pool:
        yield from pool.map(_work, jobs, chunksize=1)
