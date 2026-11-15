"""Reading a han-compose web export, and the check that this project reads each glyph as that
export records it.

An export (`han_compose.web_export`, format 6) keeps a record per key under `g/<hhh>.json`, keyed
by the SHA-256 of the key's UTF-8. A character's record holds `G`, its own glyph: `v`, 1 when the
style's first font draws it, and `p`, per contour the pen commands and the points at weight 400 as
little-endian int16 in units of 1/`quant`, base64.
"""

import base64
import gzip
import hashlib
import json
import re
import struct
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .. import identifiers as I
from ..outline import Chain, Contour, Q
from ..schema import Json

FORMAT = 6
_SHARD = re.compile(r"[0-9a-f]{3}")


def key_hash(key: str) -> str:
    """The name a record is filed under: the SHA-256 of its key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def manifest(export: Path) -> Json:
    """The export's manifest, refused unless it is of the format this module reads and states the
    fonts it was written from, its point grid and how many records it holds."""
    path = export / "manifest.json"
    if not path.is_file():
        raise ValueError(f"{export} is not a han-compose export: it has no manifest.json.")
    value: Json = json.loads(path.read_text(encoding="utf-8"))
    if value.get("format") != FORMAT:
        raise ValueError(f"{export} is an export of format {value.get('format')}; this reads format {FORMAT}.")
    try:
        (
            value["composer"]["font_sha256"],
            value["quant"],
            value["files"]["records"]["entries"],
            value["files"]["records"]["files"],
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"The manifest of {export} does not state {error}.") from error
    return value


def shard(export: Path, name: str) -> dict[str, Json]:
    """The records of `g/<name>.json`, by key hash; none when the export has no such shard."""
    path = export / "g" / f"{name}.json"
    if not path.exists():
        return {}
    raw = path.read_bytes()
    value: dict[str, Json] = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    return value


def recorded(glyph: Json) -> list[Contour]:
    """A `G` record's contours at weight 400: pen commands, and points in units of 1/`quant`."""
    out = []
    for letters, light, _heavy in glyph["p"]:
        data = base64.b64decode(light)
        out.append((letters, list(struct.unpack(f"<{len(data) // 2}h", data))))
    return out


def coarsened(contours: Iterable[Contour], quant: int) -> list[Contour]:
    """Contours in hundredths of a unit brought to units of 1/`quant`, each point to the nearest."""
    return [(letters, [round(value * quant / Q) for value in points]) for letters, points in contours]


@dataclass
class Parity:
    """How an export's glyph records compare with the outlines read from the pinned fonts."""

    whole: bool = True  #: whether every shard of the export was read
    shards: int = 0  #: shards read
    records: int = 0  #: records in them
    stated: tuple[int, int] = (0, 0)  #: the shards and records the export's manifest states
    glyphs: int = 0  #: of the records read, those with a glyph
    compared: int = 0  #: glyph records whose key a selector of the chain hashes to
    same: int = 0  #: of them, identical contour for contour and point for point
    different: list[str] = field(default_factory=list)  #: selectors whose contours differ
    other_face: list[str] = field(default_factory=list)  #: selectors the export takes from another font

    @property
    def complete(self) -> bool:
        """Whether what was read is all the export says it holds; true of a pass over named shards."""
        return not self.whole or (self.shards, self.records) == self.stated

    @property
    def exact(self) -> bool:
        """Whether the export was read whole, held a glyph record, and every one was found and
        reproduced."""
        return self.complete and 0 < self.glyphs == self.compared == self.same and not self.other_face


def parity(export: Path, chain: Chain, shards: Iterable[str] | None = None) -> Parity:
    """Compare every glyph record of a han-compose export, or those of the named shards, with the
    contours this project reads for the same character from the same fonts, on the export's grid of
    1/`quant` unit.

    The export must have been written from the chain's own font files; its manifest records their
    digests. A pass over the whole export also requires the shards and records the manifest states."""
    about = manifest(export)
    theirs, ours = set(about["composer"]["font_sha256"].values()), {face.row["sha256"] for face in chain.faces}
    if theirs != ours:
        raise ValueError(f"{export} was written from other font files than the chain {chain.name}.")
    quant: int = about["quant"]
    wanted = None if shards is None else set(shards)
    if wanted is not None and not all(_SHARD.fullmatch(name) for name in wanted):
        raise ValueError("A shard is named by three lower-case hex digits.")
    filed: dict[str, list[tuple[str, str]]] = {}
    for selector in chain.selectors():
        name = key_hash(I.selected(selector) or "")
        if wanted is None or name[:3] in wanted:
            filed.setdefault(name[:3], []).append((name, selector))
    counts = about["files"]["records"]
    out = Parity(whole=wanted is None, stated=(counts["files"], counts["entries"]))
    present = {path.stem for path in (export / "g").glob("*.json")}
    for prefix in sorted(present if wanted is None else wanted & present):
        records = shard(export, prefix)
        out.shards += 1
        out.records += len(records)
        out.glyphs += sum("G" in record for record in records.values())
        for name, selector in filed.get(prefix, ()):
            glyph = records.get(name, {}).get("G")
            face = chain.face(selector)
            if glyph is None or face is None:
                continue
            out.compared += 1
            if glyph["v"] != (1 if face is chain.faces[0] else 0):
                out.other_face.append(selector)
            if coarsened(face.contours(selector) or [], quant) == recorded(glyph):
                out.same += 1
            else:
                out.different.append(selector)
    return out
