"""The Adobe-Japan1 glyphs that CHISE's descriptions name, as rows of the component tables.

CHISE writes a glyph of the Adobe-Japan1 collection that has no code point of its own as an
entity, `&AJ1-01815;`: CID 1815. Adobe's kanji table says which character each CID is a glyph of:
the kanji of JIS X 0208 it is the base glyph of, the code point the UniJIS CMap gives it, or the
variation sequence registered for it. Each entity gives two rows: the entity is the CID, and the
CID is a glyph of a character.
"""

import gzip
import json
import re
from pathlib import Path

from . import identifiers as I
from . import pins
from .schema import COMPONENT_KINDS, Json

_ENTITY = re.compile(r"&AJ1-([0-9]+);")
_SEQUENCE = re.compile(r"<U\+([0-9A-F]+),U\+([0-9A-F]+)>")
_POINT = re.compile(r"U\+([0-9A-F]+)")


def table(path: Path) -> dict[int, list[str]]:
    """Adobe's `aj17-kanji.txt` by CID: the 21 fields of each line."""
    out = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 21:
            raise ValueError(f"aj17-kanji.txt: {len(fields)} fields in the line of CID {fields[0]}.")
        out[int(fields[0])] = fields
    return out


def glyph_of(fields: list[str]) -> tuple[str, str, str]:
    """The character a CID is a glyph of, as a component reference, with what the relation rests
    on and its kind: `jis` (the base glyph of a JIS X 0208 kanji), `code-point` (a later addition
    the UniJIS CMap maps to a code point of its own) or `sequence` (reached only by a variation
    sequence).

    A CID that the CMap maps to several code points (a Kangxi radical beside its ideograph) goes
    by the base of its variation sequence, which is the ideograph."""
    cid, jis, cmap, sequences = fields[0], fields[1], fields[17], fields[19]
    sequence = _SEQUENCE.search(sequences)
    points = _POINT.findall(cmap) if cmap != "*" else []
    if not points:
        if sequence is None:
            raise ValueError(f"aj17-kanji.txt: CID {cid} has neither a code point nor a variation sequence.")
        target = I.component("u", f"{sequence[1]}.{sequence[2]}")
        return target, f"aj17-kanji.txt field 20: the variation sequence <U+{sequence[1]},U+{sequence[2]}>", "sequence"
    point = sequence[1] if sequence is not None and sequence[1] in points else points[0]
    target = I.component("u", point)
    mapped = "UniJIS-UTF32-H maps the CID to " + ", ".join(f"U+{other}" for other in points)
    if jis != "*":
        return target, f"aj17-kanji.txt field 2: the base glyph of JIS X 0208 {jis}; field 18: {mapped}", "jis"
    return target, f"aj17-kanji.txt field 18: {mapped}", "code-point"


def rows(entities: list[str], kanji: dict[int, list[str]]) -> list[Json]:
    """Two rows of the component tables per entity `&AJ1-NNNNN;`: the entity is the CID (CHISE's
    name for it), and the CID is a glyph of a character (Adobe's table)."""
    out: list[Json] = []
    for text in entities:
        match = _ENTITY.fullmatch(text)
        if match is None:
            raise ValueError(f"{text} is not an Adobe-Japan1 entity.")
        cid = int(match[1])
        if cid not in kanji:
            raise ValueError(f"aj17-kanji.txt has no CID {cid}.")
        entity, glyph = I.component_of(text), I.component("aj1", str(cid))
        target, basis, _ = glyph_of(kanji[cid])
        out.append(_row(entity, text, "same", glyph, "the entity's name gives the CID", "source", "chise"))
        out.append(_row(glyph, "", "glyph-of", target, basis, "source", "adobe-japan1"))
    return out


def _row(component: str, text: str, relation: str, target: str, basis: str, tier: str, source: str) -> Json:
    kind = COMPONENT_KINDS[I.split_component(component)[0]]
    return {
        "component": component,
        "kind": kind,
        "text": text,
        "relation": relation,
        "target": target,
        "basis": basis,
        "tier": tier,
        "source": source,
    }


def entities(cache: Path | None = None) -> list[str]:
    """The Adobe-Japan1 entities of the pinned component registry, by CID."""
    paths = pins.source_paths(pins.source("ids-input-components"), cache, fetch=False)
    registry = json.loads(gzip.decompress(paths["custom-components.json.gz"].read_bytes()))
    found = [row["text"] for row in registry["components"] if _ENTITY.fullmatch(row["text"])]
    return sorted(found, key=lambda text: int(text[5:-1]))


def pinned(cache: Path | None = None) -> list[Json]:
    """The rows for every Adobe-Japan1 entity of the pinned registry, from the pinned table."""
    paths = pins.source_paths(pins.source("adobe-japan1"), cache, fetch=False)
    return rows(entities(cache), table(paths["aj17-kanji.txt"]))
