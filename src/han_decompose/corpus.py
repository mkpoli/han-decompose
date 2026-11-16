"""ids-input's description corpus (`data/ids-corpus.json.gz`), as pinned in `pins/sources.json`.

It is read, never bundled: the candidate descriptions of a character, the class-member rows and the
identifiers of the components it names.
"""

import gzip
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from . import pins
from .schema import Json


@dataclass(frozen=True)
class Corpus:
    """The parts of the corpus the build reads."""

    #: The component identifiers the corpus holds, `bsp:42` and `chise:CDP-8958`.
    names: frozenset[str]
    #: Each description row, as `(subject, text, resolved, status)`: the subject's identifier (`ucs:793E`),
    #: the text as the source wrote it, the text with unencoded components as `&cid;` where it differs
    #: from `text`, and `ready`, `unresolved`, `unsupported` or `empty`. In the corpus's order.
    descriptions: tuple[tuple[str, str, str | None, str], ...]
    #: The `class-member` rows of `equivalences`, as `(member, target, basis, place, tier)`, each side a
    #: corpus identifier.
    members: tuple[tuple[str, str, str, str, str], ...]


@cache
def read(cache_folder: Path | None = None) -> Corpus:
    """The pinned corpus, read from the cache."""
    paths = pins.source_paths(pins.source("ids-corpus"), cache_folder, fetch=False)
    value: Json = json.loads(gzip.decompress(paths["ids-corpus.json.gz"].read_bytes()))
    return Corpus(
        frozenset(row[0] for row in value["components"]["rows"]),
        tuple((row[0], row[1], row[2], row[6]) for row in value["descriptions"]["rows"]),
        tuple(
            (row[0], row[1], row[3], row[4], row[5])
            for row in value["equivalences"]["rows"]
            if row[2] == "class-member"
        ),
    )


def reference(cid: str) -> str | None:
    """The component reference (`docs/format.md`, 2.5) of a corpus identifier: `ucs:793E` is `u:793E`,
    and `bsp:42`, `chise:CDP-8958` and `x:X-00777` are themselves. None for any other."""
    kind, _, value = cid.partition(":")
    if kind == "ucs":
        return f"u:{value}"
    return cid if kind in ("bsp", "chise", "x") else None
