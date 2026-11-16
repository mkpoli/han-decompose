"""Classes: components that are one thing in different shapes, under a canonical member.

A row says that a member is another component drawn another way, at a place or anywhere. The rows
come from the pinned corpus's `class-member` rows and from `review/classes.tsv`, the project's own
reviewed ones. A member resolves by following its rows to a component that is no member of anything
at that place; a row with a place applies only there. A member that leads to two canonical members
at one place, or back to itself, is in no class (`docs/format.md`, 5.3).
"""

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from . import corpus
from . import identifiers as I
from .resources import resource
from .schema import Json

#: The place of each position a corpus row names. `partial` names a position no operand stands in,
#: so a row with it applies nowhere and is left out.
PLACES = {"left": "L", "right": "R", "top": "T", "bottom": "B"}


@dataclass(frozen=True)
class Row:
    """One row of the class table."""

    member: str
    target: str
    place: str
    basis: str
    tier: str
    note: str = ""


class Classes:
    """The class table: members, targets and the canonical member each leads to."""

    def __init__(self, rows: Iterable[Row]) -> None:
        self.rows = sorted(set(rows), key=lambda row: (row.member, row.place, row.target, row.basis))
        self._by_member: dict[str, list[Row]] = {}
        for row in self.rows:
            self._by_member.setdefault(row.member, []).append(row)
        self._leads: dict[tuple[str, str], frozenset[str] | None] = {}

    def _follow(self, member: str, place: str, above: tuple[str, ...] = ()) -> frozenset[str] | None:
        """The canonical members a member leads to at a place; None where the rows lead back round."""
        if (member, place) in self._leads and not above:
            return self._leads[member, place]
        if member in above:
            return None
        targets = {row.target for row in self._by_member.get(member, ()) if row.place in ("", place)}
        found: set[str] = {member} if not targets else set()
        for target in sorted(targets):
            led = self._follow(target, place, (*above, member))
            if led is None:
                return None
            found |= led
        out = frozenset(found)
        if not above:
            self._leads[member, place] = out
        return out

    def canonical(self, member: str, place: str = "") -> str:
        """The canonical member of a component at a place; the component itself when it is in no
        class there."""
        led = self._follow(member, place)
        return next(iter(led)) if led is not None and len(led) == 1 else member

    def members(self, canonical: str, place: str = "") -> list[str]:
        """Every member of a class at a place, its canonical member first."""
        found = [
            member for member in self._by_member if member != canonical and self.canonical(member, place) == canonical
        ]
        return [canonical, *sorted(found)]

    def problems(self) -> list[str]:
        """The rows that lead to no one canonical member."""
        out = []
        for member in sorted(self._by_member):
            for place in sorted({row.place for row in self._by_member[member]}):
                led = self._follow(member, place)
                if led is None:
                    out.append(f"{member}{' at ' + place if place else ''}: its rows lead back to it.")
                elif len(led) > 1:
                    out.append(f"{member}{' at ' + place if place else ''}: it leads to {', '.join(sorted(led))}.")
        return out

    def table(self) -> list[Json]:
        """The rows of `classes.tsv` (`docs/format.md`, 5.3): every row that leads to one canonical
        member, with where it leads at the row's place."""
        out = []
        for row in self.rows:
            led = self._follow(row.member, row.place)
            if led is None or len(led) != 1:
                continue
            (canonical,) = led
            out.append({**row.__dict__, "canonical": canonical, "place": row.place})
        return out


def corpus_rows(source: corpus.Corpus) -> list[Row]:
    """The class-member rows of the corpus, each side as a component reference. A row whose place
    is no operand's place is left out."""
    out = []
    for member, target, basis, place, tier in source.members:
        a, b = corpus.reference(member), corpus.reference(target)
        if a is None or b is None or (place and place not in PLACES):
            continue
        out.append(Row(a, b, PLACES.get(place, ""), basis, tier))
    return out


def editorial_rows(path: Path | None = None) -> list[Row]:
    """The rows of `review/classes.tsv`: `member`, `target`, `place`, `note`, `reviewer` and `at`."""
    path = path or resource("review") / "classes.tsv"
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file, delimiter="\t"))
    out = []
    for row in rows:
        I.split_component(row["member"])
        I.split_component(row["target"])
        out.append(
            Row(row["member"], row["target"], row["place"], "editorial", "editorial", f"{row['note']}; {row['at']}")
        )
    return out


@cache
def pinned(cache_folder: Path | None = None) -> Classes:
    """The class table of the pinned corpus and the reviewed rows."""
    return Classes([*corpus_rows(corpus.read(cache_folder)), *editorial_rows()])
