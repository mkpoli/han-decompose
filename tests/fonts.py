"""A small TrueType font built in memory, and the pinned fonts where the cache holds them."""

from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables._c_m_a_p import cmap_format_14
from fontTools.ttLib.tables.TupleVariation import TupleVariation

from han_decompose import pins
from han_decompose.outline import Chain, Face
from han_decompose.schema import Json

SQUARE = [(0, 0), (0, 512), (512, 512), (512, 0)]


def _polygon(pen: TTGlyphPen, points: list[tuple[int, int]]) -> None:
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()


def build(
    path: Path,
    upem: int = 1024,
    extra: dict[int, str] | None = None,
    sequences: dict[int, list[tuple[int, str | None]]] | None = None,
    variable: bool = False,
) -> Path:
    """A font with a square (`一`), a shape closed by a curve (`丿`), a contour of off-curve points
    only (`〇`), a composite of the square and the curve (`二`), a glyph without ink (space), and a
    variation sequence of `一` with a glyph of its own and one that keeps the base glyph. `sequences`
    adds variation sequences. A `variable` font has a `wght` axis from 100 to 900 along which the
    square's upper edge rises by 512 units."""
    names = [".notdef", "space", "square", "curve", "ring", "pair", "square.alt"]
    glyphs = {}
    for name in (".notdef", "space"):
        glyphs[name] = TTGlyphPen(None).glyph()
    pen = TTGlyphPen(None)
    _polygon(pen, SQUARE)
    glyphs["square"] = pen.glyph()
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((300, 0))
    pen.qCurveTo((301, 150), (250, 301), (100, 0))
    pen.closePath()
    glyphs["curve"] = pen.glyph()
    pen = TTGlyphPen(None)
    pen.qCurveTo((0, 0), (0, 16), (16, 16), (16, 0), None)
    pen.closePath()
    glyphs["ring"] = pen.glyph()
    pen = TTGlyphPen(glyphs)
    pen.addComponent("curve", (1, 0, 0, 1, 0, 600))
    pen.addComponent("square", (1, 0, 0, 1, 10, 0))
    glyphs["pair"] = pen.glyph()
    pen = TTGlyphPen(None)
    _polygon(pen, [(0, 0), (0, 256), (512, 256), (512, 0)])
    glyphs["square.alt"] = pen.glyph()
    cmap = {0x20: "space", 0x4E00: "square", 0x4E3F: "curve", 0x3007: "ring", 0x4E8C: "pair", **(extra or {})}
    builder = FontBuilder(upem, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    bearings = {"curve": 100, "pair": 10}
    builder.setupHorizontalMetrics({name: (512 if name == "space" else upem, bearings.get(name, 0)) for name in names})
    builder.setupHorizontalHeader(ascent=880, descent=-120)
    builder.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    if variable:
        builder.setupFvar([("wght", 100, 100, 900, "Weight")], [])
        # Deltas for the square's four points, then the four phantom points.
        risen = [(0, 0), (0, 512), (0, 512), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
        builder.setupGvar({"square": [TupleVariation({"wght": (0, 1, 1)}, risen)]})
    table = cmap_format_14(14)
    table.platformID, table.platEncID, table.language = 0, 5, 0
    table.cmap = {}
    table.uvsDict = {0xE0100: [(0x4E00, "square.alt")], 0xE0101: [(0x4E00, None)], 0xFE00: [(0x9FFF, None)]}
    for selector, pairs in (sequences or {}).items():
        table.uvsDict.setdefault(selector, []).extend(pairs)
    builder.font["cmap"].tables.append(table)
    builder.save(path)
    return path


def row(identifier: str, upem: int = 1024) -> Json:
    return {"id": identifier, "upem": upem}


def pinned_chain(name: str) -> Chain:
    """A pinned chain, or a skip when its fonts are not in the cache (`han-decompose fetch`)."""
    cache = pins.cache_root() / "fonts"
    missing = [font["file"] for font in pins.chain(name) if not (cache / font["file"]).exists()]
    if missing:
        pytest.skip(f"not in the cache: {', '.join(missing)}")
    return Chain.pinned(name)


def pinned_face(identifier: str) -> Face:
    """A pinned font, or a skip when it is not in the cache."""
    if not (pins.cache_root() / "fonts" / pins.font(identifier)["file"]).exists():
        pytest.skip(f"not in the cache: {identifier}")
    return Face.pinned(identifier)
