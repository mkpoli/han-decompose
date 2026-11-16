"""Structures: a character's descriptions reduced to canonical trees (`docs/format.md`, 2.6).

Two descriptions share a structure when they are built from the same components in the same
arrangement, however each component is drawn. The canonical tree follows glyph-atlas's decision
0012: a part that spells a character is that character, a ⿰ or ⿱ chain flattens, and every
component is written as its class's canonical member at the place it stands (礻 at the left is 示).
A character's candidates are the distinct canonical trees of all its descriptions in the corpus.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from . import classes, corpus, ids
from . import identifiers as I
from .descriptions import name_components

Tree = str | tuple[str, tuple["Tree", ...]]

#: An approximate (〾) or subtracting (㇯) description, or one with a part no character names (？),
#: describes no composition.
UNUSABLE = frozenset("〾㇯？")
#: A variation selector after a component: a structure has no stroke design.
_VARIATION = re.compile("[︀-️\U000e0100-\U000e01ef]")
#: What a component of a structure is: one character, or a token `&…;`. Stroke letters, dots and
#: other marks of the form and stroke levels are none.
_LEAF = re.compile(r"[^\x00-\x7f]|&[^&;\s]+;")
#: The operators a chain flattens in, and what it flattens into.
FLATTENING = {"⿰": "⿲", "⿱": "⿳"}
#: How many times a tree is read again, and how many times the names are collected again; both settle
#: within a few.
PASSES = 8


def tree(node: ids.Node) -> Tree:
    """A parsed description as a tree of strings and tuples."""
    return node.text if node.leaf else (node.operator or "", tuple(tree(child) for child in node.children))


def text(value: Tree) -> str:
    """A tree written back as a description."""
    return value if isinstance(value, str) else value[0] + "".join(text(part) for part in value[1])


def parsed(description: str, names: frozenset[str]) -> Tree | None:
    """A corpus description as a tree of the structure level, or None where it has no such tree:
    it names a component the corpus gives no identifier, does not read, holds a mark of the form or
    stroke level, is approximate or subtracting, or is one component."""
    named, unnamed = name_components(ids.without_notes(description), names)
    if unnamed is not None or UNUSABLE & set(named):
        return None
    try:
        node = ids.parse(_VARIATION.sub("", named))
    except ValueError:
        return None
    if node.leaf or any(not _LEAF.fullmatch(leaf.text) for leaf in ids.leaves(node)):
        return None
    return tree(node)


def _flatten(operator: str, parts: tuple[Tree, ...]) -> Tree:
    """`⿱X⿱YZ` and `⿱⿱XYZ` are `⿳XYZ`, and the same for ⿰ and ⿲."""
    three = FLATTENING.get(operator)
    if three and len(parts) == 2:
        first, second = parts
        if not isinstance(second, str) and second[0] == operator:
            return three, (first, *second[1])
        if not isinstance(first, str) and first[0] == operator:
            return three, (*first[1], second)
    return operator, parts


class Reader:
    """Reads descriptions as canonical trees with a class table and the characters whose
    descriptions are spelled out (`named`)."""

    def __init__(self, table: classes.Classes, named: dict[str, str] | None = None) -> None:
        self.table = table
        self.named = named or {}

    def _leaf(self, component: str, place: str) -> str:
        try:
            reference = I.component_of(component)
        except ValueError:
            return component
        member = self.table.canonical(reference, place)
        return component if member == reference else I.written(member) or component

    def _read(self, node: Tree, place: str, whole: bool) -> Tree:
        if isinstance(node, str):
            return self._leaf(node, place)
        operator, parts = node
        read = tuple(self._read(part, ids.place(operator, index), False) for index, part in enumerate(parts))
        found = _flatten(operator, read)
        # A part that spells a character is that character; the whole description is never renamed.
        if not whole and (char := self.named.get(text(found))) is not None:
            return char
        return found

    def canonical(self, node: Tree) -> Tree:
        """The structure a parsed description writes: read again until it is stable."""
        current = node
        for _ in range(PASSES):
            following = self._read(current, "", True)
            if following == current:
                break
            current = following
        return current


@dataclass(frozen=True)
class Candidates:
    """The structures of every character the corpus describes."""

    #: Each character's distinct canonical structures, as texts, in the corpus's order.
    by_char: dict[str, list[str]]
    #: The character each spelled-out structure names.
    named: dict[str, str]
    #: How many description rows named a character and read as a structure.
    rows: int


def build(source: corpus.Corpus, table: classes.Classes) -> Candidates:
    """Every character's candidates. A structure names the character with the lowest code point
    among those whose descriptions are that structure, and the names are collected again until a
    reading no longer changes them."""
    pairs: dict[str, list[Tree]] = {}
    rows = 0
    for subject, description, resolved, status in source.descriptions:
        # An unresolved row names a CHISE entity by the identifier the corpus gives it, and reads.
        if status not in ("ready", "unresolved") or not subject.startswith("ucs:"):
            continue
        found = parsed(resolved or description, source.names)
        if found is not None:
            rows += 1
            pairs.setdefault(chr(int(subject[4:], 16)), []).append(found)
    unique = {char: list(dict.fromkeys(found)) for char, found in pairs.items()}
    named: dict[str, str] = {}
    by_char: dict[str, list[str]] = {}
    for _ in range(PASSES):
        reader = Reader(table, named)
        by_char = {
            char: list(dict.fromkeys(text(reader.canonical(found)) for found in many)) for char, many in unique.items()
        }
        following: dict[str, str] = {}
        for char in sorted(by_char, key=ord):
            for spelled in by_char[char]:
                following.setdefault(spelled, char)
        if following == named:
            break
        named = following
    return Candidates(by_char, named, rows)


@cache
def pinned(cache_folder: Path | None = None) -> Candidates:
    """The candidates of the pinned corpus under the pinned class table."""
    return build(corpus.read(cache_folder), classes.pinned(cache_folder))
