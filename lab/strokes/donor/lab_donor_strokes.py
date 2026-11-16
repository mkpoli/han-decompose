#!/usr/bin/env -S uv run --with scikit-image,shapely,scipy,numpy,pillow python
"""Cut every donor glyph into brush strokes several ways, for side-by-side reading.

Each method is only a rule for labelling the ink's pixels with a stroke index.
Everything after that is shared: the labels become polygons, each polygon is
clipped to the glyph's real outline and to what earlier strokes have not taken,
and the remaining slivers go to their nearest stroke. So every method tiles the
same silhouette exactly, and the figures differ only in where the cut falls.

Writes demo/donor-strokes-lab.json, read by donor-strokes-lab.html.

Stroke data: KanjiVG (https://kanjivg.tagaini.net/), Ulrich Apel, CC BY-SA 3.0.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from skimage.graph import MCP_Geometric
from skimage.morphology import medial_axis
from skimage.segmentation import watershed

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cut_donor_strokes as base  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "demo" / "donor-parts-review.json"
OUT = ROOT / "demo" / "donor-strokes-lab.json"

# Pixels across the longer side of a group's box. The cut lines are interior, so
# this only has to resolve a neck, not the silhouette.
RASTER = 512


# ------------------------------------------------------------------- the canvas


class Canvas:
    """One leaf group's ink as a raster, with its stroke guide placed on it."""

    def __init__(self, ink, guide):
        self.ink = ink
        self.box = ink.bounds
        self.scale = RASTER / max(self.box[2] - self.box[0], self.box[3] - self.box[1])
        self.mask = base.rasterise(ink, self.box, self.scale)
        self.rows, self.columns = np.nonzero(self.mask)
        samples = [base.sample_stroke(d) for _, d in guide]
        placed = base.fit(samples, self.box)
        self.lines = [self.to_pixels(points) for points in placed]
        self.count = len(guide)
        # Euclidean distance to the silhouette: large in a stroke's body, small
        # at a neck where two strokes meet.
        self.edt = ndimage.distance_transform_edt(self.mask)

    def to_pixels(self, points: np.ndarray) -> np.ndarray:
        """Glyph coordinates to (row, column) raster coordinates."""
        if not len(points):
            return np.zeros((0, 2))
        column = (points[:, 0] - self.box[0]) * self.scale + 0.5
        row = (self.box[3] - points[:, 1]) * self.scale + 0.5
        return np.column_stack([row, column])

    @property
    def pixels(self) -> np.ndarray:
        return np.column_stack([self.rows, self.columns]).astype(float) + 0.5

    def stroke_owner(self) -> tuple[cKDTree, np.ndarray]:
        tree = cKDTree(np.vstack(self.lines))
        owner = np.concatenate(
            [np.full(len(line), i + 1, dtype=np.int32) for i, line in enumerate(self.lines)]
        )
        return tree, owner

    def paint(self, values: np.ndarray) -> np.ndarray:
        labels = np.zeros(self.mask.shape, dtype=np.int32)
        labels[self.rows, self.columns] = values
        return labels

    def grow(self, seeds: np.ndarray) -> np.ndarray:
        """Give every ink pixel the label of the nearest seeded pixel."""
        if not seeds.any():
            return np.zeros_like(seeds)
        _, (row, column) = ndimage.distance_transform_edt(seeds == 0, return_indices=True)
        grown = seeds[row, column]
        grown[~self.mask] = 0
        return grown

    def ridge_markers(self) -> np.ndarray:
        """A seed per stroke: its centre line where it runs inside the ink alone."""
        markers = np.zeros(self.mask.shape, dtype=np.int32)
        height, width = self.mask.shape
        tree, owner = self.stroke_owner()
        for index, line in enumerate(self.lines):
            row = np.clip(np.round(line[:, 0] - 0.5).astype(int), 0, height - 1)
            column = np.clip(np.round(line[:, 1] - 0.5).astype(int), 0, width - 1)
            inside = self.mask[row, column]
            # Where two strokes cross, the pixels under both belong to neither seed.
            _, nearest = tree.query(np.column_stack([row, column]).astype(float) + 0.5)
            inside &= owner[nearest] == index + 1
            if not inside.any():
                continue
            depth = self.edt[row, column]
            # A pixel on the silhouette is no seed: the flood has to start in the body.
            keep = inside & (depth >= 1.0)
            if not keep.any():
                keep = inside & (depth == depth[inside].max())
            markers[row[keep], column[keep]] = index + 1
        # A stroke left without a seed keeps the deepest pixel of its own centre line.
        for index, line in enumerate(self.lines):
            if (markers == index + 1).any():
                continue
            row = np.clip(np.round(line[:, 0] - 0.5).astype(int), 0, height - 1)
            column = np.clip(np.round(line[:, 1] - 0.5).astype(int), 0, width - 1)
            inside = self.mask[row, column]
            if not inside.any():
                continue
            best = np.argmax(np.where(inside, self.edt[row, column], -1))
            markers[row[best], column[best]] = index + 1
        return markers

    def branch_seeds(self) -> np.ndarray:
        """Skeleton branches, cut at junctions, each wired to its KanjiVG stroke."""
        skeleton = medial_axis(self.mask)
        if not skeleton.any():
            return np.zeros(self.mask.shape, dtype=np.int32)
        neighbours = ndimage.convolve(
            skeleton.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), mode="constant"
        ) - skeleton.astype(np.uint8)
        junction = skeleton & (neighbours >= 3)
        # Widening the junction by one pixel actually severs the branches that meet there.
        junction = ndimage.binary_dilation(junction, np.ones((3, 3), bool)) & skeleton
        branches, total = ndimage.label(skeleton & ~junction, structure=np.ones((3, 3), int))
        tree, owner = self.stroke_owner()
        seeds = np.zeros(self.mask.shape, dtype=np.int32)
        for index in range(1, total + 1):
            row, column = np.nonzero(branches == index)
            if len(row) < 2:
                continue
            _, nearest = tree.query(np.column_stack([row, column]).astype(float) + 0.5)
            votes = owner[nearest]
            seeds[row, column] = np.bincount(votes).argmax()
        # A stroke no branch spoke for keeps a seed of its own, or it would vanish.
        for index in range(self.count):
            if (seeds == index + 1).any():
                continue
            line = self.lines[index]
            row = np.clip(np.round(line[:, 0] - 0.5).astype(int), 0, self.mask.shape[0] - 1)
            column = np.clip(np.round(line[:, 1] - 0.5).astype(int), 0, self.mask.shape[1] - 1)
            inside = self.mask[row, column]
            if not inside.any():
                continue
            best = np.argmax(np.where(inside, self.edt[row, column], -1))
            seeds[row[best], column[best]] = index + 1
        return seeds

    def width(self) -> float:
        """The glyph's own stroke width here, in pixels: twice the median ink depth."""
        skeleton, depth = medial_axis(self.mask, return_distance=True)
        values = depth[skeleton]
        return float(2 * np.median(values)) if len(values) else 4.0

    def neck_lines(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Where the outline pinches: straight cuts between facing notches.

        A notch is a corner the outline turns into the ink at — exactly what a
        brush stroke leaves where it crosses another. Two notches facing each
        other across a narrow passage are the ends of one clean cut.
        """
        width = self.width() / self.scale
        reach = max(4.0, 0.45 * width)
        limit = 1.6 * width
        notches: list[tuple[float, float]] = []
        for polygon in getattr(self.ink, "geoms", [self.ink]):
            if polygon.geom_type != "Polygon":
                continue
            for ring in [polygon.exterior, *polygon.interiors]:
                coords = np.asarray(ring.coords)[:-1]
                if len(coords) < 8:
                    continue
                closed = np.vstack([coords, coords[:1]])
                along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(closed, axis=0).T))])
                total = along[-1]
                if total <= 4 * reach:
                    continue

                def at(distance, along=along, closed=closed, total=total):
                    distance = np.mod(distance, total)
                    return np.column_stack(
                        [np.interp(distance, along, closed[:, 0]),
                         np.interp(distance, along, closed[:, 1])]
                    )

                # Neighbours a fixed arc away, so a flattened curve does not read as a corner.
                middle = (at(along[:-1] - reach) + at(along[:-1] + reach)) / 2
                # The chord across a notch leaves the ink; the chord across a convex
                # corner stays inside it.
                outside = np.array(
                    [not self.ink.contains(Point(point)) for point in middle], dtype=bool
                )
                # One notch per corner. Neighbouring corner vertices belong to the same
                # corner only while they sit within a hair of each other; two corners a
                # stroke's width apart are two notches, whatever their index.
                together = 0.3 * reach
                index = 0
                while index < len(outside):
                    if not outside[index]:
                        index += 1
                        continue
                    end = index
                    while (
                        end + 1 < len(outside)
                        and outside[end + 1]
                        and along[end + 1] - along[end] < together
                    ):
                        end += 1
                    run = range(index, end + 1)
                    sharp = max(
                        run,
                        key=lambda i: math.dist(coords[i], (middle[i][0], middle[i][1])),
                    )
                    notches.append(tuple(coords[sharp]))
                    index = end + 1
        if len(notches) < 2:
            return []
        points = np.array(notches)
        tree = cKDTree(points)
        cuts = []
        seen = set()
        for i, point in enumerate(points):
            for j in tree.query_ball_point(point, limit):
                if j == i:
                    continue
                key = (min(i, j), max(i, j))
                if key in seen:
                    continue
                line = LineString([tuple(point), tuple(points[j])])
                # A cut has to run through ink, and has to be short next to the
                # outline distance between its ends, or it is not a pinch.
                if not self.ink.covers(line):
                    continue
                seen.add(key)
                cuts.append(
                    (
                        tuple(np.round(self.to_pixels(point[None, :])[0] - 0.5).astype(int)),
                        tuple(np.round(self.to_pixels(points[j][None, :])[0] - 0.5).astype(int)),
                    )
                )
        return cuts

    def distances(self) -> np.ndarray:
        """Per stroke, every ink pixel's distance to that stroke's centre line."""
        points = self.pixels
        out = np.empty((self.count, len(points)))
        for index, line in enumerate(self.lines):
            out[index] = cKDTree(line).query(points)[0]
        return out


# ------------------------------------------------------------------ the methods


def label_nearest(canvas: Canvas) -> np.ndarray:
    tree, owner = canvas.stroke_owner()
    _, nearest = tree.query(canvas.pixels, workers=-1)
    return canvas.paint(owner[nearest])


def label_skeleton(canvas: Canvas) -> np.ndarray:
    return canvas.grow(canvas.branch_seeds())


def label_kvg_shape(canvas: Canvas) -> np.ndarray:
    distances = canvas.distances()
    length = sum(
        np.hypot(*(line[1:] - line[:-1]).T).sum() for line in canvas.lines if len(line) > 1
    )
    # Mean stroke width: the ink's area spread over the total length of its strokes.
    width = canvas.mask.sum() / length if length > 0 else 4.0
    nearest = distances.argmin(axis=0) + 1
    claimed = np.where(distances.min(axis=0) <= 0.55 * width, nearest, 0)
    seeds = canvas.paint(claimed)
    grown = canvas.grow(seeds)
    # A stroke whose band was swallowed whole falls back to its nearest-line share.
    missing = [i + 1 for i in range(canvas.count) if not (grown == i + 1).any()]
    if missing:
        values = grown[canvas.rows, canvas.columns]
        for index in missing:
            values = np.where(nearest == index, index, values)
        grown = canvas.paint(values)
    return grown


def label_warp(canvas: Canvas) -> np.ndarray:
    """Pull each centre line onto the ink's own medial axis, then cut by nearest."""
    skeleton = medial_axis(canvas.mask)
    if not skeleton.any():
        return label_nearest(canvas)
    row, column = np.nonzero(skeleton)
    tree = cKDTree(np.column_stack([row, column]).astype(float) + 0.5)
    warped = []
    for line in canvas.lines:
        if len(line) < 2:
            warped.append(line)
            continue
        _, nearest = tree.query(line)
        target = tree.data[nearest]
        shift = target - line
        # Smoothing the displacement along the stroke keeps the stroke's own shape:
        # it moves onto the ink without folding onto every skeleton wobble.
        window = max(3, (len(line) // 6) | 1)
        kernel = np.ones(window) / window
        smooth = np.column_stack(
            [np.convolve(np.pad(shift[:, k], (window // 2,), mode="edge"), kernel, "valid")[: len(line)]
             for k in (0, 1)]
        )
        warped.append(line + smooth)
    owner = np.concatenate(
        [np.full(len(line), i + 1, dtype=np.int32) for i, line in enumerate(warped)]
    )
    _, nearest = cKDTree(np.vstack(warped)).query(canvas.pixels, workers=-1)
    return canvas.paint(owner[nearest])


def label_neck_cut(canvas: Canvas) -> np.ndarray:
    """Cut straight across every notch pair, then name the pieces by their stroke."""
    cuts = canvas.neck_lines()
    broken = canvas.mask.copy()
    if cuts:
        from PIL import Image, ImageDraw

        image = Image.new("1", (broken.shape[1], broken.shape[0]), 0)
        draw = ImageDraw.Draw(image)
        for (row_a, column_a), (row_b, column_b) in cuts:
            # Run the cut a little past both notches, or the ink stays joined by the
            # corner pixel at either end.
            step = np.array([row_b - row_a, column_b - column_a], dtype=float)
            step /= max(1e-6, np.hypot(*step)) / 2.5
            draw.line(
                [
                    (column_a - step[1], row_a - step[0]),
                    (column_b + step[1], row_b + step[0]),
                ],
                fill=1,
                width=3,
            )
        broken &= ~np.array(image, dtype=bool)
    pieces, total = ndimage.label(broken, structure=np.ones((3, 3), int))
    tree, owner = canvas.stroke_owner()
    _, nearest = tree.query(canvas.pixels, workers=-1)
    whole = np.bincount(owner[nearest], minlength=canvas.count + 1)
    seeds = np.zeros(canvas.mask.shape, dtype=np.int32)
    for index in range(1, total + 1):
        row, column = np.nonzero(pieces == index)
        if not len(row):
            continue
        _, near = tree.query(np.column_stack([row, column]).astype(float) + 0.5)
        votes = owner[near]
        # A stroke holds part of a piece only if most of the stroke lies in it. The
        # tail a stroke pokes across a cut — a vertical's foot inside the crossbar —
        # belongs to the piece's own stroke, not to the one it came from.
        counts = np.bincount(votes, minlength=canvas.count + 1)
        share = counts / np.maximum(whole, 1)
        present = [i for i in range(1, canvas.count + 1) if share[i] >= 0.3]
        if len(present) <= 1:
            seeds[row, column] = present[0] if present else int(np.argmax(share[1:]) + 1)
            continue
        inside = np.concatenate([canvas.lines[i - 1] for i in present])
        belongs = np.concatenate(
            [np.full(len(canvas.lines[i - 1]), i, dtype=np.int32) for i in present]
        )
        _, pick = cKDTree(inside).query(np.column_stack([row, column]).astype(float) + 0.5)
        seeds[row, column] = belongs[pick]
    return canvas.grow(seeds)


def label_neck_watershed(canvas: Canvas) -> np.ndarray:
    """Flood from each stroke's centre line; the fronts meet in the ink's valleys."""
    return watershed(-canvas.edt, markers=canvas.ridge_markers(), mask=canvas.mask)


def label_hybrid(canvas: Canvas) -> np.ndarray:
    """KanjiVG wires the skeleton branches; the watershed snaps the boundary to the neck."""
    return watershed(-canvas.edt, markers=canvas.branch_seeds(), mask=canvas.mask)


def label_geodesic(canvas: Canvas) -> np.ndarray:
    """Nearest stroke by travel inside the ink: a cut cannot jump the outline."""
    markers = canvas.ridge_markers()
    cost = np.where(canvas.mask, 1.0, np.inf)
    best = np.full(canvas.mask.shape, np.inf)
    labels = np.zeros(canvas.mask.shape, dtype=np.int32)
    for index in range(canvas.count):
        starts = np.argwhere(markers == index + 1)
        if not len(starts):
            continue
        costs, _ = MCP_Geometric(cost).find_costs([tuple(s) for s in starts])
        closer = costs < best
        best = np.where(closer, costs, best)
        labels = np.where(closer, index + 1, labels)
    labels[~canvas.mask] = 0
    return labels


METHODS = [
    (
        "nearest",
        "Nearest centre line",
        "Every ink pixel goes to the closest point of a KanjiVG stroke's centre line.",
        label_nearest,
    ),
    (
        "skeleton",
        "Skeleton branches",
        "Skeletonise the ink, cut the skeleton at its junctions, and grow each branch's "
        "territory out to the outline.",
        label_skeleton,
    ),
    (
        "kvgshape",
        "KanjiVG stroke shapes",
        "Thicken each centre line to the glyph's mean stroke width, intersect with the ink, "
        "then hand the remainder to the nearest claimed band.",
        label_kvg_shape,
    ),
    (
        "warp",
        "Warped centre lines",
        "Pull each centre line onto the ink's medial axis with a smoothed displacement, "
        "keeping the stroke's shape, then cut by nearest.",
        label_warp,
    ),
    (
        "neckcut",
        "Notch-pair neck cut",
        "Find the corners the outline turns inward at, cut straight between the facing "
        "pairs, and give each piece whole to the stroke it lies under.",
        label_neck_cut,
    ),
    (
        "neckws",
        "Neck watershed",
        "Flood outwards from every stroke's centre line; the fronts meet where the ink "
        "is narrowest.",
        label_neck_watershed,
    ),
    (
        "hybrid",
        "Wired neck watershed",
        "KanjiVG's stroke order wires the skeleton branches, then the flood puts every "
        "boundary on a neck.",
        label_hybrid,
    ),
    (
        "geodesic",
        "In-ink geodesic",
        "Nearest stroke measured by travel inside the ink, so no region reaches across "
        "a gap in the silhouette.",
        label_geodesic,
    ),
]


# ----------------------------------------------------------------- the shared tail


def finish(labels: np.ndarray, canvas: Canvas) -> list:
    """Labels to polygons that tile the ink exactly, as cut_donor_strokes does."""
    raw = base.regions_from_labels(labels, canvas.count, canvas.box, canvas.scale)
    ink = canvas.ink
    taken = None
    regions: list = []
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
    leftover = (ink if taken is None else ink.difference(taken)).buffer(0)
    if not leftover.is_empty and leftover.area > 0:
        tree, owner = canvas.stroke_owner()
        for piece in getattr(leftover, "geoms", [leftover]):
            if piece.is_empty or piece.area <= 0 or piece.geom_type != "Polygon":
                continue
            centre = piece.representative_point()
            point = canvas.to_pixels(np.array([[centre.x, centre.y]]))
            _, which = tree.query(point)
            index = int(owner[which[0]]) - 1
            regions[index] = piece if regions[index] is None else unary_union(
                [regions[index], piece]
            ).buffer(0)
    return regions


def check(regions: list, ink) -> dict:
    """Does this cut tile the ink? Area, overlap, spill and NaN, as fractions of the ink."""
    live = [r for r in regions if r is not None and not r.is_empty]
    total = sum(r.area for r in live)
    union = unary_union(live) if live else None
    overlap = max(0.0, total - (union.area if union else 0.0))
    outside = union.difference(ink).area if union else 0.0
    coordinates = np.concatenate(
        [np.asarray(polygon.exterior.coords) for region in live
         for polygon in getattr(region, "geoms", [region])
         if polygon.geom_type == "Polygon" and not polygon.is_empty]
    ) if live else np.zeros((0, 2))
    return {
        "area": total / ink.area if ink.area else 0.0,
        "overlap": overlap / ink.area if ink.area else 0.0,
        "outside": outside / ink.area if ink.area else 0.0,
        "nan": bool(not np.isfinite(coordinates).all()),
    }


def main() -> int:
    data = json.loads(SOURCE.read_text())
    out_entries = []
    worst: dict[str, dict] = {key: {"area": 1.0, "overlap": 0.0, "outside": 0.0, "nan": False}
                              for key, *_ in METHODS}
    for entry in data["entries"]:
        groups = []
        for group in base.groups_of(entry):
            shapes = [base.part_shape(part) for part in group["parts"]]
            ink = unary_union([s for s in shapes if s is not None])
            if ink.is_empty:
                continue
            glyph = base.leaf_glyph(group["leaf"])
            guide = None if glyph in base.SINGLE else base.leaf_strokes(glyph)
            groups.append({"leaf": group["leaf"], "ink": ink, "guide": guide, "glyph": glyph})
        if not groups:
            continue
        outline = unary_union([g["ink"] for g in groups])
        methods = []
        for key, name, note, rule in METHODS:
            pieces = []
            tiles = {"area": 0.0, "overlap": 0.0, "outside": 0.0, "nan": False}
            for group in groups:
                ink, guide = group["ink"], group["guide"]
                if not guide or len(guide) == 1:
                    kinds = [guide[0][0] if guide else base.SINGLE.get(group["glyph"], group["glyph"])]
                    regions = [ink]
                else:
                    canvas = Canvas(ink, guide)
                    regions = finish(rule(canvas), canvas)
                    kinds = [kind or "?" for kind, _ in guide]
                report = check(regions, ink)
                tiles["area"] += report["area"] * ink.area
                tiles["overlap"] += report["overlap"] * ink.area
                tiles["outside"] += report["outside"] * ink.area
                tiles["nan"] = tiles["nan"] or report["nan"]
                strokes = []
                for kind, region in zip(kinds, regions):
                    if region is None or region.is_empty:
                        continue
                    contours = base.to_commands(region)
                    if contours:
                        strokes.append({"type": kind, "path": contours})
                if strokes:
                    pieces.append({"leaf": group["leaf"], "strokes": strokes})
            for field in ("area", "overlap", "outside"):
                tiles[field] = round(tiles[field] / outline.area, 5)
            methods.append(
                {
                    "key": key,
                    "count": sum(len(p["strokes"]) for p in pieces),
                    "tiling": tiles,
                    "parts": pieces,
                }
            )
            worst[key] = {
                "area": min(worst[key]["area"], tiles["area"]),
                "overlap": max(worst[key]["overlap"], tiles["overlap"]),
                "outside": max(worst[key]["outside"], tiles["outside"]),
                "nan": worst[key]["nan"] or tiles["nan"],
            }
        out_entries.append(
            {
                "char": entry["char"],
                "ids": entry["ids"],
                "outline": [part["path"] for part in entry["parts"]],
                "methods": methods,
            }
        )
        print(
            f"{entry['char']} "
            + "  ".join(
                f"{m['key']}:{m['count']}/{m['tiling']['area']:.3f}" for m in methods
            ),
            flush=True,
        )
    OUT.write_text(
        json.dumps(
            {
                "face": data["face"],
                "raster": RASTER,
                "kvgSource": data["kvgSource"],
                "methods": [
                    {"key": key, "name": name, "note": note} for key, name, note, _ in METHODS
                ],
                "entries": out_entries,
            },
            ensure_ascii=False,
        )
    )
    print("\nworst tiling per method (area 1.000 = exact, overlap/outside 0 = clean)")
    for key, *_ in METHODS:
        w = worst[key]
        print(
            f"  {key:9s} area {w['area']:.4f}  overlap {w['overlap']:.5f}  "
            f"outside {w['outside']:.5f}  nan {w['nan']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
