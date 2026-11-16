#!/usr/bin/env -S uv run --with scikit-image,shapely,scipy,numpy,pillow python
"""Divide each donor glyph's own outline into its real brush strokes.

The guide is KanjiVG's stroke centre lines; the material is the font's own ink.
For every leaf group of a donor character the leaf's KanjiVG strokes are fitted
into the group's bounding box, sampled, and used to partition the group's ink:
the shape is rasterised, every ink pixel takes the index of the nearest sampled
stroke point, and each label's region becomes a polygon again. The regions are
then clipped against the exact outline, so together they tile the ink and the
glyph keeps its silhouette.

Writes `strokeParts` into demo/donor-parts-review.json.

Stroke data: KanjiVG (https://kanjivg.tagaini.net/), Ulrich Apel, CC BY-SA 3.0.
"""

from __future__ import annotations

import json
import math
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from skimage.measure import find_contours

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "demo" / "donor-parts-review.json"
STROKE_DIR = ROOT / ".review" / "stroke-paths"
KVG_URL = "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{code}.svg"

# Resolution of the label raster, in pixels across the longer side of a group's box.
RASTER = 1024
# Curve flattening: glyph units per segment, and KanjiVG units per sampled point.
FLATTEN_STEP = 2.0
SAMPLE_STEP = 0.3
# Output precision, in glyph units. Region boundaries are snapped to this grid
# before they are subtracted from each other, so a shared edge stays shared.
GRID = 0.1

# Where a leaf's strokes come from. A leaf KanjiVG draws on its own needs no
# entry; the rest borrow their strokes from a character that contains them, by
# KanjiVG's own element annotation or, lacking one, by stroke number.
SOURCES: dict[str, tuple[str, object]] = {
    "宓": ("密", "宓"),
    "䜌": ("巒", "䜌"),
    "𤇾": ("榮", "𤇾"),
    "𦥯": ("學", "𦥯"),
    # 学 annotates the two halves of 𰃮 separately: ⺍ over 冖.
    "𰃮": ("学", ["⺍", "冖"]),
    # 半 opens with the two strokes of 丷 but does not name them as a group.
    "丷": ("半", (1, 2)),
}
# A leaf that is itself a single stroke: nothing to cut, and KanjiVG has no file.
SINGLE = {"㇒": "㇒", "丿": "㇒", "一": "㇐", "丨": "㇑", "丶": "㇔"}
# Leaf names that carry a position or a reference number alongside the glyph.
RENAME = {"山上": "山"}


def leaf_glyph(name: str) -> str:
    """The glyph a part's leaf name refers to: '{42} 彐' and '山上' are 彐 and 山."""
    bare = re.sub(r"^\{\d+\}\s*", "", name).strip() or name
    bare = RENAME.get(bare, bare)
    return RENAME.get(name, bare)


# ---------------------------------------------------------------- KanjiVG input


def kvg_svg(char: str) -> ET.Element:
    path = STROKE_DIR / f"{char}.svg"
    if not path.exists():
        code = format(ord(char), "05x")
        STROKE_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(KVG_URL.format(code=code), timeout=30) as response:
            path.write_text(response.read().decode())
        print(f"fetched KanjiVG {char} ({code})", file=sys.stderr)
    text = path.read_text()
    # Older files declare the kvg namespace only in a DOCTYPE the stdlib parser ignores.
    if "xmlns:kvg" not in text.split("<svg", 1)[1].split(">", 1)[0]:
        text = text.replace("<svg ", '<svg xmlns:kvg="http://kanjivg.tagaini.net" ', 1)
    return ET.fromstring(text)


def strokes_in(node: ET.Element) -> list[tuple[str, str]]:
    """(type, d) for every stroke under a node, in KanjiVG's stroke order."""
    out = []
    for child in node:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "path":
            kind = next((v for k, v in child.attrib.items() if k.endswith("type")), "")
            out.append((kind, child.attrib["d"]))
        else:
            out.extend(strokes_in(child))
    return out


def element_node(root: ET.Element, element: str) -> ET.Element | None:
    for node in root.iter():
        if any(k.endswith("element") and v == element for k, v in node.attrib.items()):
            return node
    return None


def leaf_strokes(glyph: str) -> list[tuple[str, str]] | None:
    """The stroke guide for a leaf, or None when KanjiVG offers nothing."""
    if glyph in SOURCES:
        source, which = SOURCES[glyph]
        root = kvg_svg(source)
        if isinstance(which, tuple):
            first, last = which
            return strokes_in(root)[first - 1 : last]
        names = which if isinstance(which, list) else [which]
        out: list[tuple[str, str]] = []
        for name in names:
            node = element_node(root, name)
            if node is None:
                return None
            out.extend(strokes_in(node))
        return out
    if len(glyph) != 1:
        return None
    try:
        root = kvg_svg(glyph)
    except Exception:
        return None
    # The whole file is the glyph; take every stroke it draws.
    return strokes_in(root) or None


# ------------------------------------------------------------------ path geometry


TOKEN = re.compile(r"[MmLlCcSsHhVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def parse_kvg_path(d: str) -> list[list[tuple[float, float]]]:
    """Flatten a KanjiVG stroke path into polylines (KanjiVG units, y down)."""
    tokens = TOKEN.findall(d)
    polylines: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    point = (0.0, 0.0)
    start = (0.0, 0.0)
    control: tuple[float, float] | None = None
    command = ""
    index = 0

    def cubic(p0, c1, c2, p3):
        length = math.dist(p0, c1) + math.dist(c1, c2) + math.dist(c2, p3)
        steps = max(2, int(length / 0.4) + 1)
        for step in range(1, steps + 1):
            t = step / steps
            u = 1 - t
            yield (
                u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p3[1],
            )

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command in "Zz":
                if len(current) > 1:
                    current.append(start)
                    polylines.append(current)
                current = []
                control = None
                continue
            if index >= len(tokens):
                break
        # An implicit repeat of M continues with L, as SVG requires.
        if command == "M" and current:
            command = "L"
        elif command == "m" and current:
            command = "l"
        counts = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4}
        need = counts[command.upper()]
        values = [float(v) for v in tokens[index : index + need]]
        if len(values) < need:
            break
        index += need
        relative = command.islower()
        kind = command.upper()
        if kind == "M":
            point = (values[0], values[1]) if not relative else (point[0] + values[0], point[1] + values[1])
            if len(current) > 1:
                polylines.append(current)
            current = [point]
            start = point
            control = None
        elif kind in ("L", "H", "V"):
            if kind == "L":
                end = (values[0], values[1]) if not relative else (point[0] + values[0], point[1] + values[1])
            elif kind == "H":
                end = (values[0] if not relative else point[0] + values[0], point[1])
            else:
                end = (point[0], values[0] if not relative else point[1] + values[0])
            current = current or [point]
            current.append(end)
            point = end
            control = None
        else:
            if kind == "C":
                pairs = [(values[i], values[i + 1]) for i in range(0, 6, 2)]
                if relative:
                    pairs = [(point[0] + x, point[1] + y) for x, y in pairs]
                c1, c2, end = pairs
            else:
                pairs = [(values[i], values[i + 1]) for i in range(0, 4, 2)]
                if relative:
                    pairs = [(point[0] + x, point[1] + y) for x, y in pairs]
                c2, end = pairs
                c1 = (2 * point[0] - control[0], 2 * point[1] - control[1]) if control else point
            current = current or [point]
            current.extend(cubic(point, c1, c2, end))
            control = c2
            point = end
    if len(current) > 1:
        polylines.append(current)
    return polylines


def sample_stroke(d: str) -> np.ndarray:
    """Points along a KanjiVG stroke's centre line, evenly by arc length."""
    points: list[tuple[float, float]] = []
    for line in parse_kvg_path(d):
        for index in range(len(line) - 1):
            a, b = line[index], line[index + 1]
            span = math.dist(a, b)
            steps = max(1, int(span / SAMPLE_STEP))
            for step in range(steps):
                t = step / steps
                points.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        points.append(line[-1])
    return np.array(points, dtype=float) if points else np.zeros((0, 2))


def flatten_part(path: list[list]) -> list[list[tuple[float, float]]]:
    """Flatten a part's command list into closed rings (glyph units, y up)."""
    rings: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    point = (0.0, 0.0)

    def curve(points):
        # de Casteljau on a quadratic or cubic, at a step fine enough to be invisible.
        order = len(points) - 1
        length = sum(math.dist(points[i], points[i + 1]) for i in range(order))
        steps = max(2, int(length / FLATTEN_STEP) + 1)
        for step in range(1, steps + 1):
            t = step / steps
            working = list(points)
            while len(working) > 1:
                working = [
                    (
                        working[i][0] + (working[i + 1][0] - working[i][0]) * t,
                        working[i][1] + (working[i + 1][1] - working[i][1]) * t,
                    )
                    for i in range(len(working) - 1)
                ]
            yield working[0]

    for command in path:
        head = command[0]
        values = [float(v) for v in command[1:]]
        if head == "M":
            if len(current) > 2:
                rings.append(current)
            point = (values[0], values[1])
            current = [point]
        elif head == "L":
            point = (values[0], values[1])
            current.append(point)
        elif head in ("Q", "C"):
            points = [point] + [
                (values[i], values[i + 1]) for i in range(0, len(values), 2)
            ]
            current.extend(curve(points))
            point = points[-1]
        elif head == "Z":
            if len(current) > 2:
                rings.append(current)
            current = []
    if len(current) > 2:
        rings.append(current)
    return rings


def rings_to_polygon(rings: list[list[tuple[float, float]]]):
    """Glyph rings to a polygon, reading nesting depth for holes (even-odd)."""
    shells = [Polygon(ring) for ring in rings if len(ring) > 2]
    shells = [shell for shell in shells if shell.area > 0]
    if not shells:
        return None
    depth = []
    for i, shell in enumerate(shells):
        inside = 0
        for j, other in enumerate(shells):
            if i != j and other.area > shell.area and other.contains(shell.representative_point()):
                inside += 1
        depth.append(inside)
    result = []
    for i, shell in enumerate(shells):
        if depth[i] % 2:
            continue
        holes = [
            shells[j].exterior.coords
            for j in range(len(shells))
            if depth[j] == depth[i] + 1 and shell.contains(shells[j].representative_point())
        ]
        result.append(Polygon(shell.exterior.coords, holes))
    geometry = unary_union(result)
    return geometry if not geometry.is_empty else None


def part_shape(part: dict):
    return rings_to_polygon(flatten_part(part["path"]))


# --------------------------------------------------------------------- the cut


def rasterise(shape, box, scale) -> np.ndarray:
    """A boolean ink mask of a shape, one pixel per 1/scale glyph units."""
    from PIL import Image, ImageDraw

    minx, miny, maxx, maxy = box
    width = max(4, int(math.ceil((maxx - minx) * scale)) + 2)
    height = max(4, int(math.ceil((maxy - miny) * scale)) + 2)
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    polygons = shape.geoms if isinstance(shape, MultiPolygon) else [shape]

    def device(coords):
        # y flips: glyph coordinates run up, the raster runs down.
        return [((x - minx) * scale + 1, (maxy - y) * scale + 1) for x, y in coords]

    for polygon in polygons:
        draw.polygon(device(polygon.exterior.coords), fill=1)
        for hole in polygon.interiors:
            draw.polygon(device(hole.coords), fill=0)
    return np.array(image, dtype=bool)


def fit(samples: list[np.ndarray], box):
    """Map KanjiVG stroke points into a group's box, stretching each axis to fit."""
    everything = np.vstack([s for s in samples if len(s)])
    kminx, kminy = everything.min(axis=0)
    kmaxx, kmaxy = everything.max(axis=0)
    minx, miny, maxx, maxy = box
    kwidth, kheight = kmaxx - kminx, kmaxy - kminy
    width, height = maxx - minx, maxy - miny
    # A guide with no extent on one axis (a lone horizontal stroke) keeps the
    # other axis's scale, so it lands on the middle of the ink rather than
    # stretching to nothing.
    uniform = min(
        width / kwidth if kwidth > 1e-6 else math.inf,
        height / kheight if kheight > 1e-6 else math.inf,
    )
    sx = width / kwidth if kwidth > 1e-6 else uniform
    sy = height / kheight if kheight > 1e-6 else uniform
    if not math.isfinite(sx) or not math.isfinite(sy):
        sx = sy = 1.0

    def place(points: np.ndarray) -> np.ndarray:
        if not len(points):
            return points
        x = minx + (points[:, 0] - kminx) * sx + (width - kwidth * sx) / 2
        # KanjiVG draws downwards; the glyph upwards.
        y = maxy - ((points[:, 1] - kminy) * sy + (height - kheight * sy) / 2)
        return np.column_stack([x, y])

    return [place(s) for s in samples]


def snap(geometry):
    """Round a region's coordinates onto the output grid."""
    from shapely.ops import transform

    return transform(lambda x, y, z=None: (np.round(x / GRID) * GRID, np.round(y / GRID) * GRID), geometry)


def regions_from_labels(labels: np.ndarray, count: int, box, scale) -> list:
    """Each label's pixels back to a polygon, by marching squares."""
    minx, miny, maxx, maxy = box
    out = []
    for index in range(count):
        mask = (labels == index + 1).astype(float)
        if not mask.any():
            out.append(None)
            continue
        padded = np.pad(mask, 1)
        shells = []
        for contour in find_contours(padded, 0.5):
            # (row, column) in the padded raster back to glyph coordinates.
            x = (contour[:, 1] - 1.5) / scale + minx
            y = maxy - (contour[:, 0] - 1.5) / scale
            if len(x) > 3:
                shells.append(list(zip(x, y)))
        polygon = rings_to_polygon(shells)
        if polygon is None:
            out.append(None)
            continue
        # Smoothing of the raster's staircase. Two glyph units is under a third of
        # a screen pixel in the 90 px figure, and the cut line is interior: the
        # silhouette comes from the outline this region is clipped to, not from here.
        polygon = polygon.simplify(max(2.0, 1.5 / scale)).buffer(0)
        out.append(snap(polygon) if not polygon.is_empty else None)
    return out


def cut_group(ink, guide: list[tuple[str, str]]):
    """Partition one leaf group's ink along its KanjiVG strokes."""
    samples = [sample_stroke(d) for _, d in guide]
    if any(len(s) == 0 for s in samples):
        return None, "a stroke sampled to nothing"
    box = ink.bounds
    placed = fit(samples, box)
    scale = RASTER / max(box[2] - box[0], box[3] - box[1])
    mask = rasterise(ink, box, scale)
    if not mask.any():
        return None, "the ink rasterised to nothing"
    rows, columns = np.nonzero(mask)
    # Pixel centres, in glyph coordinates.
    points = np.column_stack(
        [(columns - 1 + 0.5) / scale + box[0], box[3] - (rows - 1 + 0.5) / scale]
    )
    owner = np.concatenate(
        [np.full(len(s), i + 1, dtype=np.int32) for i, s in enumerate(placed)]
    )
    tree = cKDTree(np.vstack(placed))
    _, nearest = tree.query(points, workers=-1)
    labels = np.zeros(mask.shape, dtype=np.int32)
    labels[rows, columns] = owner[nearest]
    raw = regions_from_labels(labels, len(guide), box, scale)

    # The raster is only the guide to where the cut falls. Each region is clipped
    # to the real outline, and to what earlier regions have not taken, so the
    # regions never overlap and never leave the glyph.
    taken = None
    regions = []
    for region in raw:
        if region is None:
            regions.append(None)
            continue
        piece = region.intersection(ink)
        if taken is not None:
            piece = piece.difference(taken)
        piece = piece.buffer(0)
        if piece.is_empty or piece.area <= 0:
            regions.append(None)
            continue
        regions.append(piece)
        taken = piece if taken is None else unary_union([taken, piece])

    # Whatever the raster's staircase left over — slivers along the silhouette —
    # goes to the stroke nearest to it, so the regions tile the ink exactly.
    leftover = ink if taken is None else ink.difference(taken)
    leftover = leftover.buffer(0)
    if not leftover.is_empty and leftover.area > 0:
        tree_owner = owner[:]
        for piece in leftover.geoms if hasattr(leftover, "geoms") else [leftover]:
            if piece.is_empty or piece.area <= 0 or piece.geom_type not in ("Polygon",):
                continue
            centre = piece.representative_point()
            _, which = tree.query([[centre.x, centre.y]])
            index = int(tree_owner[which[0]]) - 1
            if regions[index] is None:
                regions[index] = piece
            else:
                regions[index] = unary_union([regions[index], piece]).buffer(0)
    return regions, None


# ------------------------------------------------------------------ output shape


def to_commands(geometry) -> list[list[list]]:
    """A region to a contour list of command objects, in glyph coordinates."""
    polygons = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    contours = []
    for polygon in polygons:
        if polygon.geom_type != "Polygon" or polygon.is_empty:
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            coords = list(ring.coords)
            if len(coords) > 1 and coords[0] == coords[-1]:
                coords = coords[:-1]
            if len(coords) < 3:
                continue
            commands = [["M", round(coords[0][0], 1), round(coords[0][1], 1)]]
            commands += [["L", round(x, 1), round(y, 1)] for x, y in coords[1:]]
            commands.append(["Z"])
            contours.append(commands)
    return contours


def groups_of(entry: dict) -> list[dict]:
    """Consecutive parts sharing a leaf name are one element of the description."""
    groups: list[dict] = []
    for part in entry["parts"]:
        if groups and groups[-1]["leaf"] == part["leaf"]:
            groups[-1]["parts"].append(part)
        else:
            groups.append({"leaf": part["leaf"], "parts": [part]})
    return groups


def main() -> int:
    data = json.loads(DATA.read_text())
    uncut: list[str] = []
    report: list[str] = []
    for entry in data["entries"]:
        stroke_parts = []
        counts = []
        for group in groups_of(entry):
            shapes = [part_shape(part) for part in group["parts"]]
            ink = unary_union([s for s in shapes if s is not None])
            if ink.is_empty:
                continue
            glyph = leaf_glyph(group["leaf"])
            guide = None if glyph in SINGLE else leaf_strokes(glyph)
            if guide and len(guide) == 1:
                regions, types = [ink], [guide[0][0]]
            elif guide:
                regions, problem = cut_group(ink, guide)
                if regions is None:
                    uncut.append(f"{entry['char']} {group['leaf']} ({problem})")
                    regions, types = [ink], [glyph]
                else:
                    types = [kind or "?" for kind, _ in guide]
            elif glyph in SINGLE:
                regions, types = [ink], [SINGLE[glyph]]
            else:
                uncut.append(f"{entry['char']} {group['leaf']} (no KanjiVG strokes)")
                regions, types = [ink], [glyph]
            strokes = []
            for kind, region in zip(types, regions):
                if region is None or region.is_empty:
                    continue
                contours = to_commands(region)
                if contours:
                    strokes.append({"type": kind, "path": contours})
            if strokes:
                stroke_parts.append({"leaf": group["leaf"], "strokes": strokes})
                counts.append(f"{group['leaf']}:{len(strokes)}")
        entry["strokeParts"] = stroke_parts
        # kvgStrokes and leafStrokes were the Strokes column's old inputs and go.
        # geomStrokes stays: it is what the Recursive end figure draws.
        for field in ("kvgStrokes", "leafStrokes"):
            entry.pop(field, None)
        total = sum(len(group["strokes"]) for group in stroke_parts)
        report.append(f"{entry['char']} {entry['ids']}  {total} strokes  {' '.join(counts)}")
    data["strokeMethod"] = (
        f"KanjiVG stroke centre lines fitted per leaf group, ink partitioned by "
        f"nearest stroke point on a {RASTER} px raster, regions clipped to the outline"
    )
    # The file is written as one line, the shape it already had.
    DATA.write_text(json.dumps(data, ensure_ascii=False))
    print("\n".join(report))
    if uncut:
        print("\nuncut groups:")
        print("\n".join(f"  {line}" for line in uncut))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
