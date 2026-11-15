"""The filled check: 1 − IoU between a cut and its component drawn alone, each stretched on its
own to fill a 64 × 64 grid.

On the cuts of 山 judged by eye the right ones reach 0.599 at worst and the wrong ones 0.636 at
best; the limit sits in that gap.
"""

from typing import Any

import numpy as np

from .. import geometry as G

LIMIT = 0.6081
#: The grid both shapes are rasterised on. A finer grid is another measure and needs its own limit.
SIDE = 64
SUB = 2
#: Segments per curve when a shape is flattened for the grid.
STEPS = 16


def rings(commands: list[list[G.Command]]) -> list[G.Array]:
    """Contours of pen commands as closed rings of points."""
    out: list[G.Array] = []
    for contour in commands:
        points: list[tuple[float, float]] = []
        current = (0.0, 0.0)
        for command in contour:
            op = command[0]
            if op in ("M", "L"):
                current = (command[1], command[2])
                points.append(current)
            elif op == "Q":
                cx, cy, x, y = command[1:5]
                x0, y0 = current
                for step in range(1, STEPS + 1):
                    t = step / STEPS
                    u = 1 - t
                    points.append((u * u * x0 + 2 * u * t * cx + t * t * x, u * u * y0 + 2 * u * t * cy + t * t * y))
                current = (x, y)
            elif op == "C":
                c1x, c1y, c2x, c2y, x, y = command[1:7]
                x0, y0 = current
                for step in range(1, STEPS + 1):
                    t = step / STEPS
                    u = 1 - t
                    points.append((
                        u**3 * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t**3 * x,
                        u**3 * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t**3 * y,
                    ))  # fmt: skip
                current = (x, y)
            elif op == "Z":
                if points and points[0] != points[-1]:
                    points.append(points[0])
        if len(points) >= 3:
            ring = np.asarray(points, dtype=float)
            if tuple(ring[0]) != tuple(ring[-1]):
                ring = np.vstack([ring, ring[:1]])
            out.append(ring)
    return out


def raster(found: list[G.Array], side: int, sub: int = SUB) -> G.Array:
    """Coverage of the ink over a `side` × `side` grid of its own box: the shape is stretched in
    x and y separately to fill the square, even-odd fill, `sub` samples per cell and axis."""
    points = np.vstack(found)
    minx, miny = float(points[:, 0].min()), float(points[:, 1].min())
    maxx, maxy = float(points[:, 0].max()), float(points[:, 1].max())
    width, height = max(maxx - minx, 1e-9), max(maxy - miny, 1e-9)
    fine = side * sub
    edges = np.vstack([np.column_stack([ring[:-1], ring[1:]]) for ring in found])
    x0 = (edges[:, 0] - minx) / width
    y0 = (edges[:, 1] - miny) / height
    x1 = (edges[:, 2] - minx) / width
    y1 = (edges[:, 3] - miny) / height
    centres = (np.arange(fine) + 0.5) / fine
    grid = np.zeros((fine, fine), dtype=np.uint8)
    for row, y in enumerate(centres):
        hit = (y0 > y) != (y1 > y)
        if not hit.any():
            continue
        crossings = np.sort(x0[hit] + (x1[hit] - x0[hit]) * (y - y0[hit]) / (y1[hit] - y0[hit]))
        grid[row] = np.searchsorted(crossings, centres, side="right") % 2
    out: Any = grid.reshape(side, sub, side, sub).mean(axis=(1, 3))
    return np.asarray(out, dtype=np.float64)


def mask(ink: G.Path) -> G.Array:
    """A shape on the grid of the filled check."""
    return raster(rings(G.commands_of(ink)), SIDE)


def iou(left: G.Array, right: G.Array) -> float:
    """Intersection over union of two rasters, a cell counting as ink above half coverage."""
    a, b = left > 0.5, right > 0.5
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0
