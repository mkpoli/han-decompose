"""Glyph outlines as the pinned fonts draw them: the contours in the font's own order, composites
decomposed, curves kept, points in hundredths of a unit on a 1000-unit em.

`docs/format.md` (4.3) states the form. The reading follows han-compose's `compose.Font.glyph` and
`web_export._ops`, so that a contour index means the same contour in both projects.
"""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, cast

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

from . import identifiers as I
from . import pins
from .schema import Json

#: A contour as the format writes it: its pen commands and its points, x and y interleaved.
Contour = tuple[str, list[int]]

EM = 1000
Q = 100


def commands(pen: Sequence[tuple[str, tuple[Any, ...]]], scale: float) -> list[Contour]:
    """A recorded glyph as contours: `M`, `L`, `C`, `Q<n>`, and `Q<n>*` for a contour without an
    on-curve point; each coordinate times `scale`, rounded to the nearest integer, ties to even."""
    out: list[Contour] = []
    letters = ""
    points: list[int] = []
    for name, arguments in pen:
        if name in ("closePath", "endPath"):
            out.append((letters, points))
            letters, points = "", []
            continue
        real = [point for point in arguments if point is not None]
        if name == "moveTo":
            letters += "M"
        elif name == "lineTo":
            letters += "L"
        elif name == "curveTo":
            letters += "C"
        elif name == "qCurveTo":
            letters += f"Q{len(real)}" + ("*" if arguments[-1] is None else "")
        else:
            raise ValueError(f"A glyph is not drawn with {name}.")
        for x, y in real:
            points += [round(x * scale), round(y * scale)]
    return out


class Face:
    """One pinned font, opened at the instance its registry row names."""

    def __init__(self, row: Json, path: Path):
        self.row = row
        self.id: str = row["id"]
        with path.open("rb") as file:
            collection = file.read(4) == b"ttcf"
        if collection != ("index" in row):
            raise ValueError(f"{self.id}: a pin names a face index exactly when its file is a collection.")
        self.font = TTFont(path, fontNumber=row.get("index", -1))
        try:
            self.upem: int = self.font["head"].unitsPerEm
            if self.upem != row["upem"]:
                raise ValueError(f"{self.id} has {self.upem} units per em, its pin says {row['upem']}.")
            instance: dict[str, float] = row.get("instance", {})
            axes = (
                {axis.axisTag: (axis.minValue, axis.maxValue) for axis in self.font["fvar"].axes}
                if "fvar" in self.font
                else {}
            )
            for tag, value in instance.items():
                if tag not in axes or not axes[tag][0] <= value <= axes[tag][1]:
                    raise ValueError(f"{self.id} has no axis {tag} that reaches {value:g}.")
            if axes and not instance:
                raise ValueError(f"{self.id} is a variable font; its pin names no instance.")
        except ValueError:
            self.font.close()
            raise
        self._glyphs = self.font.getGlyphSet(location=instance) if instance else self.font.getGlyphSet()
        self._cmap: dict[int, str] = self.font.getBestCmap()
        #: Variation sequences the font maps: (base, selector) → glyph name, None for the base's own glyph.
        self._sequences: dict[tuple[int, int], str | None] = {
            (base, selector): name
            for table in self.font["cmap"].tables
            if table.format == 14
            for selector, pairs in table.uvsDict.items()
            for base, name in pairs
        }
        self._scale = EM * Q / self.upem

    @classmethod
    def pinned(cls, identifier: str, cache: Path | None = None, fetch: bool = False) -> "Face":
        """The pinned font `identifier` from the cache, its digest checked."""
        row = pins.font(identifier)
        return cls(row, pins.font_path(row, cache, fetch))

    def close(self) -> None:
        """Close the font file."""
        self.font.close()

    def glyph_name(self, selector: str) -> str | None:
        """The glyph a selector reaches in this font, or None when the font does not map it. A
        variation sequence is drawn only where the font maps that sequence."""
        match = I.SELECTOR.fullmatch(selector)
        if match is None:
            raise ValueError(f"{selector!r} is not a glyph selector.")
        if match["gid"] is not None:
            index = int(match["gid"])
            return cast(str, self.font.getGlyphName(index)) if index < self.font["maxp"].numGlyphs else None
        base = int(match["base"], 16)
        if match["selector"] is None:
            return self._cmap.get(base)
        sequence = (base, int(match["selector"], 16))
        return (self._sequences[sequence] or self._cmap.get(base)) if sequence in self._sequences else None

    def selectors(self) -> Iterator[str]:
        """Every code point and variation sequence the font maps, as selectors."""
        for point in sorted(self._cmap):
            yield f"U+{point:04X}"
        for base, selector in sorted(self._sequences):
            if self._sequences[base, selector] is not None or base in self._cmap:
                yield f"U+{base:04X}.{selector:04X}"

    def contours(self, selector: str) -> list[Contour] | None:
        """The contours of the glyph a selector reaches, in the font's order; None when the font
        does not map the selector. A glyph without ink has none."""
        name = self.glyph_name(selector)
        if name is None:
            return None
        pen = DecomposingRecordingPen(self._glyphs)
        self._glyphs[name].draw(pen)
        return commands(pen.value, self._scale)

    def advance(self, selector: str) -> float | None:
        """The advance width of the glyph a selector reaches, in units of the 1000-unit em."""
        name = self.glyph_name(selector)
        return None if name is None else round(self._glyphs[name].width * EM / self.upem, 2)


class Chain:
    """The fonts one design is spread over, in the order a glyph is looked for."""

    def __init__(self, name: str, faces: Sequence[Face]):
        self.name = name
        self.faces = list(faces)

    @classmethod
    def pinned(cls, designs: str | Sequence[str], cache: Path | None = None, fetch: bool = False) -> "Chain":
        """The fonts of the pinned design, or of several in order, from the cache, each font's digest
        checked."""
        names = [designs] if isinstance(designs, str) else list(designs)
        rows = [row for name in names for row in pins.chain(name)]
        return cls("+".join(names), [Face(row, pins.font_path(row, cache, fetch)) for row in rows])

    def __enter__(self) -> "Chain":
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def close(self) -> None:
        """Close every font file of the chain."""
        for face in self.faces:
            face.close()

    def face(self, selector: str) -> Face | None:
        """The first font of the chain that maps the selector. A variation sequence is taken from
        the first font that maps the sequence, which may come after one that maps its base alone."""
        return next((face for face in self.faces if face.glyph_name(selector) is not None), None)

    def selectors(self) -> Iterator[str]:
        """Every selector some font of the chain maps, once, in the order of the chain."""
        seen: set[str] = set()
        for face in self.faces:
            for selector in face.selectors():
                if selector not in seen:
                    seen.add(selector)
                    yield selector
