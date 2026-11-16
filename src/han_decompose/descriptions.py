"""The description tables of the three pinned sources, read as each source writes them.

Each source writes a description in its own notation and may attach tags to it. A table keeps every
description of a subject in the source's order; the first is the one a reading takes unless told
otherwise.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from . import corpus, ids, pins

SOURCES = ("babelstone", "chise", "zi-tools")
#: The table of canonical structures the corpus gives (`structures.py`), which the cutters read.
CORPUS = "ids-corpus"

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
    #: The first component the text names that the corpus gives no identifier, as the source wrote it.
    unnamed: str | None = None

    @property
    def structure(self) -> str:
        """The text the format's structure is of: the description without the notes zi.tools adds."""
        return ids.without_notes(self.text) if self.source == "zi-tools" else self.text

    def tree(self) -> ids.Node:
        """The description as a tree; ValueError when it does not read as one, and `Unnamed` when it
        names a component the corpus gives no identifier."""
        if self.unnamed is not None:
            raise Unnamed(f"{self.unnamed} has no identifier in the corpus.")
        return ids.parse(ids.without_notes(self.text) if self.source == "zi-tools" else self.text)


class Unnamed(ValueError):
    """A description that names a component no identifier of the corpus stands for."""


_NUMBER_TOKEN = re.compile(r"\{([0-9]+)\}")
_ENTITY = re.compile(r"&([^&;\s]+);")
_CHAIN = re.compile(r"#\([^()]*(?:\([^()]*\)[^()]*)*\)")


def token(name: str, names: frozenset[str] | None = None) -> str | None:
    """A component as one source writes it, `{42}` or `&CDP-8958;`, as the token of its corpus
    identifier, `&bsp:42;` or `&chise:CDP-8958;`; None where `names`, the identifiers the corpus
    holds, has none, and for a stroke chain, which the corpus does not name."""
    if match := _NUMBER_TOKEN.fullmatch(name):
        cid = f"bsp:{match[1]}"
    elif match := _ENTITY.fullmatch(name):
        cid = match[1] if match[1].startswith(("bsp:", "chise:")) else f"chise:{match[1]}"
    else:
        return None
    return f"&{cid};" if names is None or cid in names else None


def name_components(text: str, names: frozenset[str] | None = None) -> tuple[str, str | None]:
    """A description with its numbered components and entities written as tokens of the corpus's
    identifiers, and the first component that has none, as the source wrote it."""
    unnamed: str | None = None

    def one(match: re.Match[str]) -> str:
        nonlocal unnamed
        found = token(match[0], names)
        if found is None:
            unnamed = unnamed or match[0]
            return match[0]
        return found

    out = _ENTITY.sub(one, _NUMBER_TOKEN.sub(one, text))
    if unnamed is None and (chain := _CHAIN.search(out)):
        unnamed = chain[0]
    return out, unnamed


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
    #: The component identifiers of the corpus; None accepts every numbered component and entity.
    names: frozenset[str] | None = None

    def add(self, subject: str, text: str, tags: str | None = None) -> None:
        """Add a description. A text the source gives twice for a subject is one description,
        with the tags of each occurrence joined by a space."""
        text, unnamed = name_components(text, self.names)
        rows = self.rows.setdefault(subject, [])
        for index, row in enumerate(rows):
            if row.text == text:
                joined = " ".join(part for part in (row.tags, tags) if part) or None
                rows[index] = Description(self.source, subject, text, joined, unnamed)
                return
        rows.append(Description(self.source, subject, text, tags, unnamed))

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


def babelstone(path: Path, names: frozenset[str] | None = None) -> Table:
    """IDS.TXT: every sequence between `^` and `$` with its region letters, the maintainer's `*`
    notes left out, and the numbered components of note 6."""
    table = Table("babelstone", names=names)
    for line in _lines(path):
        if line.startswith("#\t{"):
            match = _NUMBERED.fullmatch(line)
            if match is None or (match["char"] and f"{ord(match['char']):04X}" != match["point"]):
                raise ValueError(f"IDS.TXT: the numbered component in {line!r} does not read.")
            written = match["written"]
            name = f"&bsp:{match['name'][1:-1]};"
            table.numbered[name] = Numbered(
                name,
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


def chise(paths: Iterable[Path], names: frozenset[str] | None = None) -> Table:
    """CHISE's IDS-UCS files: the third field of a line, and each `@apparent=` field after it as
    a description of its own."""
    table = Table("chise", names=names)
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


def zi_tools(path: Path, names: frozenset[str] | None = None) -> Table:
    """Yi Bai's `ids_lv1.txt`: every alternative of every field, fields being split at `;`."""
    table = Table("zi-tools", names=names)
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
def corpus_names(cache_folder: Path | None = None) -> frozenset[str]:
    """The identifiers of the components the pinned corpus holds, `bsp:42` and `chise:CDP-8958`."""
    return corpus.read(cache_folder).names


@cache
def table(source: str, cache_folder: Path | None = None) -> Table:
    """The pinned table of a description source, read from the cache. `CORPUS` is every character's
    canonical structures, one description each, with no source or tag."""
    if source == CORPUS:
        return _corpus_table(cache_folder)
    if source not in SOURCES:
        raise KeyError(f"{source} is not a description source.")
    paths = pins.source_paths(pins.source(source), cache_folder, fetch=False)
    names = corpus_names(cache_folder)
    if source == "babelstone":
        return babelstone(paths["IDS.TXT"], names)
    if source == "chise":
        return chise(paths.values(), names)
    return zi_tools(paths["ids_lv1.txt"], names)


def _corpus_table(cache_folder: Path | None) -> Table:
    from . import structures

    out = Table(CORPUS, names=corpus_names(cache_folder))
    # Whether a component stands for a character is a fact of note 6 of IDS.TXT, which the corpus keeps
    # as components and not as characters.
    out.numbered = table("babelstone", cache_folder).numbered
    for char, found in structures.pinned(cache_folder).by_char.items():
        for structure in found:
            out.add(char, structure)
    return out
