"""The description tables of the three pinned sources, read as each source writes them.

`docs/format.md` (2.3) states what a description's text is in each source and what the source
attaches to it. A table keeps every description of a subject in the source's order; the first is
the one a reading takes unless told otherwise.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from . import identifiers as I
from . import ids, pins

SOURCES = ("babelstone", "chise", "zi-tools")

_BABELSTONE = re.compile(r"\^(?P<ids>[^$]+)\$(?:\((?P<regions>[^)]*)\))?")
_NUMBERED = re.compile(
    r"#\t(?P<name>\{[0-9]+\})\t(?:(?P<where>.*) \((?P<point>[0-9A-F]{4,6}) (?P<char>.)\)\t(?P<written>.*))?"
)
_CHISE_SUBJECT = re.compile(r"U[+-][0-9A-F]+", re.IGNORECASE)


@dataclass(frozen=True)
class Description:
    """One description of a subject: the text the format hashes, and what the source attaches."""

    source: str
    subject: str
    text: str
    tags: str | None = None

    @property
    def id(self) -> str:
        return I.description_id(self.source, self.text)

    def tree(self) -> ids.Node:
        """The description as a tree; ValueError when it does not read as one."""
        return ids.parse(ids.without_notes(self.text) if self.source == "zi-tools" else self.text)


@dataclass(frozen=True)
class Numbered:
    """A numbered component of BabelStone IDS (note 6 of IDS.TXT): where the note says it occurs,
    its character in the private use area of BabelStone Han PUA, and the fragment the note writes
    it out as, None where the note gives `？` or nothing."""

    name: str
    where: str
    pua: str
    written: str | None


@dataclass
class Table:
    """The descriptions of one source by subject, as the subject is written."""

    source: str
    rows: dict[str, list[Description]] = field(default_factory=dict)
    numbered: dict[str, Numbered] = field(default_factory=dict)

    def add(self, subject: str, text: str, tags: str | None = None) -> None:
        self.rows.setdefault(subject, []).append(Description(self.source, subject, text, tags))

    def of(self, subject: str) -> list[Description]:
        return self.rows.get(subject, [])

    def first(self, subject: str) -> Description | None:
        found = self.rows.get(subject)
        return found[0] if found else None

    def glyph(self, text: str) -> str | None:
        """The one character a component is drawn as alone: the component itself when it is a
        character, or the single character note 6 writes a numbered component out as."""
        if text in self.numbered:
            text = self.numbered[text].written or ""
        return ids.character(text)


def _lines(path: Path) -> list[str]:
    return [line.rstrip("\r") for line in path.read_text(encoding="utf-8-sig").split("\n")]


def babelstone(path: Path) -> Table:
    """IDS.TXT: every sequence between `^` and `$` with its region letters, the maintainer's `*`
    notes left out, and the numbered components of note 6."""
    table = Table("babelstone")
    for line in _lines(path):
        if match := _NUMBERED.fullmatch(line):
            written = match["written"]
            table.numbered[match["name"]] = Numbered(
                match["name"],
                match["where"] or "",
                match["char"] or "",
                written if written and written != "？" else None,
            )
        if not line.startswith("U+"):
            continue
        point, char, *sequences = line.split("\t")
        if f"U+{ord(char):04X}" != point:
            raise ValueError(f"IDS.TXT writes {point} as {char!r}.")
        for sequence in sequences:
            if sequence.startswith("*"):
                continue
            found = _BABELSTONE.fullmatch(sequence.strip())
            if found is None:
                raise ValueError(f"IDS.TXT: {point} has the unreadable sequence {sequence!r}.")
            table.add(char, found["ids"], found["regions"] or None)
    return table


def chise(paths: Iterable[Path]) -> Table:
    """CHISE's IDS-UCS files: the third field of a line, and each `@apparent=` field after it as
    a description of its own."""
    table = Table("chise")
    for path in sorted(paths, key=lambda path: path.name):
        for line in _lines(path):
            fields = line.split("\t")
            if len(fields) < 3 or not _CHISE_SUBJECT.fullmatch(fields[0]) or len(fields[1]) != 1:
                continue
            if fields[2]:
                table.add(fields[1], fields[2])
            for extra in fields[3:]:
                if extra.startswith("@apparent=") and extra[10:]:
                    table.add(fields[1], extra[10:], "apparent")
    return table


def zi_tools(path: Path) -> Table:
    """Yi Bai's `ids_lv1.txt`: every alternative of every field, fields being split at `;`."""
    table = Table("zi-tools")
    for line in _lines(path):
        char, *columns = line.split("\t")
        if len(char) != 1:
            continue
        for column in columns:
            for part in column.split(";"):
                if part.strip():
                    table.add(char, part.strip())
    return table


@cache
def table(source: str, cache_folder: Path | None = None) -> Table:
    """The pinned table of a description source, read from the cache."""
    paths = pins.source_paths(pins.source(source), cache_folder, fetch=False)
    if source == "babelstone":
        return babelstone(paths["IDS.TXT"])
    if source == "chise":
        return chise(paths.values())
    if source == "zi-tools":
        return zi_tools(paths["ids_lv1.txt"])
    raise KeyError(f"{source} is not a description source.")
