"""GlyphWiki's drawn glyphs as a font of the format: the registry row `glyphwiki@<dump date>`, the
glyph each name selects, and the outline of a drawing with its contours grouped per stroke.

The engine's polygons are in KAGE's frame, 200 units with y down. They are written on the
1000-unit em with y up (the frame's height less y, times 5, in hundredths of a unit), each
polygon turned to run clockwise so that a fill of the whole glyph agrees with a fill of any one
stroke. The contours are the engine's polygons, one per contour, in the order the engine draws
them.
"""

import json
from typing import Any

import pathops

from . import glyphwiki as gw
from . import identifiers as I
from . import pins
from .outline import Contour
from .pieces import Glyph, assemble
from .schema import Json

#: KAGE's frame is 200 units on the 1000-unit em, and a unit is 100 in the file.
SCALE = 5 * 100
FRAME = 200


def font_row(dump: gw.Dump) -> Json:
    """The registry row of the font the dump makes: GlyphWiki's glyphs drawn by the KAGE engine
    the build pins."""
    engine = json.loads((gw.KAGE_CLI.parents[1] / "pin.json").read_text(encoding="utf-8"))
    source = pins.source("glyphwiki")
    return {
        "id": I.font_id("glyphwiki", dump.date),
        "name": "GlyphWiki",
        "version": dump.date,
        "file": "dump.tar.gz",
        "url": dump.url,
        "sha256": dump.sha256,
        "upem": gw.UPEM,
        "licence": source["licence"],
        "licenceEvidence": source["licenceEvidence"],
        "licenceFile": source["licenceFile"],
        "copyright": source["attribution"],
        "style": "serif",
        "design": "glyphwiki",
        "grain": "contour",
        "renderer": {"engine": "kage-engine", "commit": engine["commit"], "style": "mincho", "route": "makeGlyph3"},
    }


def selector_of(name: str) -> str | None:
    """The selector a GlyphWiki name is filed under: the code point alone for `uXXXX`, with its
    variation selector for `uXXXX-uE01XX`, else the name. None for a name the format cannot spell."""
    info = gw.name_info(name)
    if info is None:
        return None
    if info.suffix is None:
        return info.selector_spelling
    try:
        return I.name_selector(name)
    except ValueError:
        return None


def contour(polygon: tuple[tuple[float, float], ...]) -> list[tuple[int, int]]:
    """A polygon on the em in hundredths of a unit, running clockwise."""
    points = [(round(x * SCALE), round((FRAME - y) * SCALE)) for x, y in polygon]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, [*points[1:], *points[:1]], strict=True))
    return points[::-1] if area > 0 else points


def glyph_of(font: str, selector: str, drawing: gw.Drawing) -> Glyph:
    """The glyph a drawing is: its polygons as contours, and the pieces they divide into."""
    contours: list[Contour] = []
    paths: list[Any] = []
    outline = pathops.Path()
    for item in drawing.contours:
        points = contour(item.points)
        flat = [value for point in points for value in point]
        contours.append(("M" + "L" * (len(points) - 1), flat))
        path = pathops.Path()
        for target in (path.getPen(), outline.getPen()):
            for index, (x, y) in enumerate(points):
                (target.moveTo if index == 0 else target.lineTo)((x / 100, y / 100))
            target.closePath()
        paths.append(path)
    out = assemble(font, selector, contours, paths, outline, gw.UPEM * 5)
    out.strokes = [
        {
            "type": stroke.type % 100,
            **({"option": stroke.type // 100} if stroke.type >= 100 else {}),
            "contours": list(stroke.contours),
        }
        for stroke in drawing.strokes
        if stroke.contours
    ]
    return out


class Drawn:
    """GlyphWiki's drawings as `outlines.write_block` reads a font's: by selector."""

    def __init__(self, font: str, drawings: dict[str, gw.Drawing]):
        self.id = font
        self.drawings = drawings
        self.kept: dict[Any, Any] = {}

    def glyph(self, selector: str) -> Glyph | None:
        drawing = self.drawings.get(selector)
        return None if drawing is None else glyph_of(self.id, selector, drawing)
