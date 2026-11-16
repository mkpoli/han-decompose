"""The files of a release as `docs/format.md` lays them out: outline shards and cut shards, each
written the one way the format allows, so that a rebuild gives the same bytes."""

import gzip
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import __version__, pins
from . import identifiers as I
from .pieces import Glyph
from .schema import Json
from .tsv import number

OUTLINES = "han-decompose/outlines@2.0"
STROKES = "han-decompose/strokes@2.0"
CUTS = "han-decompose/cuts@2.0"
FORMS = "han-decompose/forms@2.0"
LIBRARY = "han-decompose/library@2.0"
FONTS = "han-decompose/fonts@2.0"
MANIFEST = "han-decompose/manifest@2.0"


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


def compressed(text: str) -> bytes:
    """A file's text as gzip with its modification time at 0."""
    return gzip.compress(text.encode("utf-8"), 9, mtime=0)


def write(path: Path, text: str) -> None:
    """Write a file's text; a `.gz` name is gzip with its modification time at 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed(text) if path.suffix == ".gz" else text.encode("utf-8"))


def _selector(row: Json) -> str | None:
    """The selector a reading or a skipped attempt is filed under: its glyph's, or its subject's
    own where no font draws the subject; None for a subject that is no character."""
    if "glyph" in row:
        return I.split_glyph_id(row["glyph"])[1]
    kind, value = I.split_component(row["subject"])
    return f"U+{value}" if kind == "u" else None


def change_notice(row: Json) -> str | None:
    """What a font whose licence asks that a changed copy say how and when it was changed says in
    each file of its data: the Arphic Public License. Files hold no date, so that a rebuild gives
    the same bytes; the change is dated by the release that carries the file."""
    if row["licence"] != "Arphic-1999":
        return None
    return (
        f"Changed from {row['name']} {row['version']} by han-decompose {__version__} when the release "
        "named in manifest.json was built. Every glyph this file holds, whether it is every glyph the font "
        "maps or a selection, keeps each contour in the font's order, with its points scaled from "
        f"{row['upem']} to 1000 units per em and rounded to hundredths of a unit, and with its pieces and box "
        "added; a stroke file adds outlines cut from those contours. Under the Arphic Public License, as the "
        "font is."
    )


def outline_head(font: str, row: Json | None = None) -> Json:
    """An outline file without its glyphs: the font, its licence and copyright line, and, for a
    font whose licence asks that a changed copy say how it was changed, that notice. `row` is the
    font's registry row, read from the registry where not given."""
    row = row or pins.font(font)
    head: Json = {"format": OUTLINES, "font": font, "licence": row["licence"], "copyright": row["copyright"]}
    if notice := change_notice(row):
        head["notice"] = notice
    return {**head, "em": 1000, "q": 100, "glyphs": {}}


def _design_of(cut: str) -> str:
    """The design of the font a cut's glyph is of."""
    design: str = pins.font(I.split_glyph_id(I.split_cut_id(cut)[0])[0])["design"]
    return design


def _score(reading: Json) -> float:
    """How well a reading's cuts fit: the mean of their `fit` or `match`, 0 where they give none."""
    scores = [
        float(cut["evidence"].get("fit", cut["evidence"].get("match", 0)))
        for cut in reading["cuts"]
        if "evidence" in cut
    ]
    return sum(scores) / len(scores) if scores else 0.0


def reviewed(reading: Json) -> bool:
    """Whether a person judged every cut of a reading right: a reviewer's pick."""
    return bool(reading["cuts"]) and all(cut["status"] == "reviewed-right" for cut in reading["cuts"])


def choose(readings: list[Json], keep: bool = False) -> list[Json]:
    """The readings with `chosen` set: of those of one structure on one layer of one glyph that are
    accepted, the reviewer's pick, else the one with the best fit, an earlier method name breaking a
    tie; no other. With `keep`, a reading already chosen stands unless a reviewer picked another."""
    groups: dict[tuple[str, tuple[str, ...], str], list[int]] = {}
    for at, row in enumerate(readings):
        groups.setdefault((row["glyph"], tuple(row["layer"]), row["structure"]), []).append(at)
    out = [{**row, "chosen": False} for row in readings]
    for members in groups.values():
        accepted = [
            at
            for at in members
            if readings[at]["cuts"]
            and all(cut["status"] in ("accepted", "reviewed-right") for cut in readings[at]["cuts"])
        ]
        if not accepted:
            continue
        picked = [at for at in accepted if reviewed(readings[at])]
        held = [at for at in accepted if keep and readings[at].get("chosen")]
        standing = [at for at in held if at in picked] if picked else held
        if standing:
            out[standing[0]]["chosen"] = True
            continue
        best = min(picked or accepted, key=lambda at: (-_score(readings[at]), readings[at]["method"]["name"], at))
        out[best]["chosen"] = True
    return out


class Store:
    """Readings, skipped attempts, drawn IDS, strokes and the glyphs they name, gathered and then
    written as files."""

    def __init__(self) -> None:
        self.glyphs: dict[str, dict[str, Json]] = {}
        self.readings: dict[str, list[Json]] = {}
        self.skipped: dict[str, list[Json]] = {}
        self.drawn: dict[str, dict[str, list[Json]]] = {}
        self.strokes: dict[str, dict[str, list[Json]]] = {}
        self._read: set[tuple[str, tuple[str, ...], str, str]] = set()
        self.forms: dict[str, dict[str, dict[str, Json]]] = {}
        self.library: dict[str, dict[str, dict[str, dict[str, list[str]]]]] = {}

    def glyph(self, glyph: Glyph) -> None:
        """Keep a glyph's outline, once."""
        held = self.glyphs.setdefault(glyph.font, {})
        if glyph.selector not in held and glyph.contours:
            held[glyph.selector] = glyph.record()

    def record(self, font: str, selector: str, record: Json) -> None:
        """Keep an outline record made elsewhere."""
        self.glyphs.setdefault(font, {}).setdefault(selector, record)

    def reading(self, row: Json) -> None:
        """Keep a reading. A layer has one reading per method under a structure: the first given
        stands, so candidates that share a structure are read once."""
        font, _ = I.split_glyph_id(row["glyph"])
        key = (row["glyph"], tuple(row["layer"]), row["structure"], row["method"]["name"])
        if key not in self._read:
            self._read.add(key)
            self.readings.setdefault(font, []).append(row)

    def skip(self, row: Json, font: str) -> None:
        """Keep a skipped attempt in the files of `font`: the font of its glyph, or the first of
        the design where no font draws the subject."""
        self.skipped.setdefault(font, []).append(row)

    def draw(self, font: str, selector: str, row: Json) -> None:
        """Keep a drawn IDS of a glyph."""
        self.drawn.setdefault(font, {}).setdefault(selector, []).append(row)

    def stroke(self, font: str, selector: str, row: Json) -> None:
        """Keep the strokes of one leaf cut of a glyph."""
        self.strokes.setdefault(font, {}).setdefault(selector, []).append(row)

    def form(
        self, design: str, component: str, style: str, form: Json, library: dict[str, list[str]] | None = None
    ) -> None:
        """Keep the cut chosen as a style's form of a class in a design, and the cuts that confirm it."""
        self.forms.setdefault(design, {}).setdefault(component, {})[style] = form
        if library:
            self.library.setdefault(design, {}).setdefault(component, {})[style] = library

    def lifted(self, component: str, style: str, form: Json, library: dict[str, list[str]]) -> None:
        """Keep a lifted form in the design of the font whose glyph it was cut from, with the cuts of
        its library that come from fonts of that design."""
        design = _design_of(form["cut"])
        mine = {place: [cut for cut in cuts if _design_of(cut) == design] for place, cuts in library.items()}
        self.form(design, component, style, form, {place: cuts for place, cuts in mine.items() if cuts})

    def files(self) -> Iterable[tuple[str, Json]]:
        """Every file as its path in a release and its content, in the order of the paths."""
        out: dict[str, Json] = {}
        for font, held in self.glyphs.items():
            for selector in sorted(held, key=I.order):
                file = out.setdefault(f"outlines/{font}/{I.shard(selector)}.json.gz", outline_head(font))
                file["glyphs"][selector] = held[selector]
        for font, cut_strokes in self.strokes.items():
            row = pins.font(font)
            head = {"format": STROKES, "font": font, "licence": row["licence"], "copyright": row["copyright"]}
            if notice := change_notice(row):
                head["notice"] = notice
            for selector in sorted(cut_strokes, key=I.order):
                file = out.setdefault(f"strokes/{font}/{I.shard(selector)}.json.gz", {**head, "glyphs": {}})
                file["glyphs"][selector] = cut_strokes[selector]
        for font in sorted({*self.readings, *self.skipped, *self.drawn}):
            design = pins.font(font)["design"]

            def file_of(selector: str, font: str = font, design: str = design) -> Json:
                return out.setdefault(
                    f"cuts/{font}/{I.shard(selector)}.json.gz",
                    {"format": CUTS, "font": font, "design": design, "drawn": {}, "readings": [], "skipped": []},
                )

            def key(row: Json) -> tuple[tuple[int, int, int, str], str, list[str], str]:
                return (I.order(_selector(row) or "gid.0"), row["subject"], row["layer"], row.get("structure", ""))

            for row in sorted(choose(self.readings.get(font, [])), key=key):
                file_of(_selector(row) or "gid.0")["readings"].append(row)
            for row in sorted(self.skipped.get(font, []), key=key):
                file_of(_selector(row) or "gid.0")["skipped"].append(row)
            for selector in sorted(self.drawn.get(font, {}), key=I.order):
                file_of(selector)["drawn"][selector] = self.drawn[font][selector]
        for design, forms in self.forms.items():
            out[f"forms/{design}.json.gz"] = {"format": FORMS, "design": design, "forms": forms}
        for design, library in self.library.items():
            out[f"library/{design}.json.gz"] = {"format": LIBRARY, "design": design, "library": library}
        return sorted(out.items())

    def write(self, folder: Path) -> list[Path]:
        """Write every file under a folder; the paths written."""
        written = []
        for name, content in self.files():
            write(folder / name, dumps(content))
            written.append(folder / name)
        return written
