"""The files of a release as `docs/format.md` lays them out: outline shards and cut shards, each
written the one way the format allows, so that a rebuild gives the same bytes."""

import gzip
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import identifiers as I
from . import pins
from .pieces import Glyph
from .schema import Json
from .tsv import number

OUTLINES = "han-decompose/outlines@1.0"
CUTS = "han-decompose/cuts@1.0"
FORMS = "han-decompose/forms@1.0"
LIBRARY = "han-decompose/library@1.0"


def _encode(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, int | float):
        return number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(f"{json.dumps(key, ensure_ascii=False)}:{_encode(value[key])}" for key in sorted(value))
            + "}"
        )
    if isinstance(value, list | tuple):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    raise TypeError(f"{type(value).__name__} is not written to a data file.")


def dumps(value: Json) -> str:
    """A JSON file's text: one line, keys sorted, no spaces, characters as themselves, a whole
    number without a fraction and any other in positional decimal."""
    return _encode(value) + "\n"


def write(path: Path, text: str) -> None:
    """Write a file's text; a `.gz` name is gzip with its modification time at 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(gzip.compress(data, 9, mtime=0) if path.suffix == ".gz" else data)


def _order(selector: str) -> tuple[int, int, int]:
    match = I.SELECTOR.fullmatch(selector)
    assert match is not None
    if match["gid"] is not None:
        return (1, int(match["gid"]), 0)
    return (0, int(match["base"], 16), int(match["selector"], 16) if match["selector"] else 0)


def _selector(row: Json) -> str | None:
    """The selector a reading or a skipped attempt is filed under: its glyph's, or its subject's
    own where no font draws the subject; None for a subject that is no character."""
    if "glyph" in row:
        return I.split_glyph_id(row["glyph"])[1]
    kind, value = I.split_component(row["subject"])
    return f"U+{value}" if kind == "u" else None


def terms(font: str, source: str, guide: str | None = None) -> Json:
    """The terms a cut file states: the font's licence, the description source's, the guide's, and
    the copyright and attribution lines of each."""
    font_row, source_row = pins.font(font), pins.source(source)
    out: Json = {
        "outline": font_row["licence"],
        "description": source_row["licence"],
        "notices": [font_row["copyright"], source_row["attribution"]],
    }
    if guide is not None:
        guide_row = pins.source(guide)
        out["guide"] = guide_row["licence"]
        out["notices"].append(guide_row["attribution"])
    return out


class Store:
    """Readings, skipped attempts and the glyphs they name, gathered and then written as shards."""

    def __init__(self) -> None:
        self.glyphs: dict[str, dict[str, Json]] = {}
        self.readings: dict[tuple[str, str], list[Json]] = {}
        self.skipped: dict[tuple[str, str], list[Json]] = {}
        self.forms: dict[str, dict[str, Json]] = {}
        self.library: dict[str, dict[str, dict[str, list[str]]]] = {}

    def glyph(self, glyph: Glyph) -> None:
        """Keep a glyph's outline, once."""
        held = self.glyphs.setdefault(glyph.font, {})
        if glyph.selector not in held and glyph.contours:
            held[glyph.selector] = glyph.record()

    def record(self, font: str, selector: str, record: Json) -> None:
        """Keep an outline record made elsewhere."""
        self.glyphs.setdefault(font, {}).setdefault(selector, record)

    def reading(self, row: Json) -> None:
        font, _ = I.split_glyph_id(row["glyph"])
        self.readings.setdefault((font, row["description"].rpartition(".")[0]), []).append(row)

    def skip(self, row: Json, font: str) -> None:
        """Keep a skipped attempt in the files of `font`: the font of its glyph, or the first of
        the chain where no font draws the subject."""
        self.skipped.setdefault((font, row["description"].rpartition(".")[0]), []).append(row)

    def form(self, chain: str, component: str, form: Json, library: dict[str, list[str]]) -> None:
        """Keep the cut chosen as a component's form in a chain, and the cuts that confirm it."""
        self.forms.setdefault(chain, {})[component] = form
        if library:
            self.library.setdefault(chain, {})[component] = library

    def files(self) -> Iterable[tuple[str, Json]]:
        """Every file as its path in a release and its content, in the order of the paths."""
        out: dict[str, Json] = {}
        for font, held in self.glyphs.items():
            row = pins.font(font)
            for selector in sorted(held, key=_order):
                file = out.setdefault(
                    f"outlines/{font}/{I.shard(selector)}.json.gz",
                    {"format": OUTLINES, "font": font, "licence": row["licence"], "copyright": row["copyright"]}
                    | {"em": 1000, "q": 100, "glyphs": {}},
                )
                file["glyphs"][selector] = held[selector]
        for font, source in sorted({*self.readings, *self.skipped}):
            guides = {row["method"].get("guide") for row in self.readings.get((font, source), ())} - {None}
            if len(guides) > 1:
                raise ValueError(f"The cuts of {font} under {source} follow more than one guide.")
            head = {"format": CUTS, "font": font, "source": source, "terms": terms(font, source, *guides)}

            def key(row: Json) -> tuple[tuple[int, int, int], str, str]:
                return (_order(_selector(row) or "gid.0"), row["subject"], row["description"])

            for kind, rows in (("readings", self.readings), ("skipped", self.skipped)):
                for row in sorted(rows.get((font, source), ()), key=key):
                    file = out.setdefault(
                        f"cuts/{font}/{source}/{I.shard(_selector(row) or 'gid.0')}.json.gz",
                        {**head, "readings": [], "skipped": []},
                    )
                    file[kind].append(row)
        for chain, forms in self.forms.items():
            out[f"forms/{chain}.json.gz"] = {"format": FORMS, "chain": chain, "forms": forms}
        for chain, library in self.library.items():
            out[f"library/{chain}.json.gz"] = {"format": LIBRARY, "chain": chain, "library": library}
        return sorted(out.items())

    def write(self, folder: Path) -> list[Path]:
        """Write every file under a folder; the paths written."""
        written = []
        for name, content in self.files():
            write(folder / name, dumps(content))
            written.append(folder / name)
        return written
