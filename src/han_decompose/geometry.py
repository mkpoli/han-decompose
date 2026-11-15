"""Outlines as shapes: boolean operations, boxes and flattening.

Shapes are `pathops.Path` values on the 1000-unit em, y up. Every number a cutter decides on comes
from here, so the arithmetic is written out step by step and kept in one order: the same glyph
gives the same number on every run.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pathops

Path = Any  # pathops.Path
Box = tuple[float, float, float, float]
Array = npt.NDArray[np.float64]
Command = list[Any]

#: Ink smaller than this, in square units, is a rounding artefact of the boolean operations.
EPS_AREA = 60.0
#: Units per flattened curve segment when a shape is sampled.
FLATTEN = 4.0


def union_of(paths: Sequence[Path]) -> Path:
    """The shapes merged into one outline."""
    builder = pathops.OpBuilder()
    for path in paths:
        builder.add(path, pathops.PathOp.UNION)
    out = builder.resolve()
    out.simplify()
    return out


def filled(contour: Any) -> Path:
    """One contour on its own, as a solid shape."""
    path = pathops.Path()
    contour.draw(path.getPen())
    return path


def inside(small: Path, large: Path) -> bool:
    """Whether one shape lies within another: their common ink is the whole of the smaller."""
    common = pathops.op(small, large, pathops.PathOp.INTERSECTION)
    common.simplify()
    return bool(abs(common.area) >= 0.98 * abs(small.area))


def box_of(paths: Sequence[Path]) -> Box:
    """The box the shapes occupy together."""
    return (
        min(path.bounds[0] for path in paths),
        min(path.bounds[1] for path in paths),
        max(path.bounds[2] for path in paths),
        max(path.bounds[3] for path in paths),
    )


def segments_of(path: Path) -> list[list[tuple[str, tuple[Any, ...]]]]:
    """A path as contours of (command, points) segments, each ending on the curve."""
    contours: list[list[tuple[str, tuple[Any, ...]]]] = []
    current: list[tuple[str, tuple[Any, ...]]] | None = None
    start: Any = None
    for verb, points in path.segments:
        if verb == "moveTo":
            current = []
            contours.append(current)
            start = points[0]
        elif current is None:
            continue
        elif verb == "lineTo":
            current.append(("L", (points[0],)))
        elif verb == "curveTo":
            current.append(("C", tuple(points)))
        elif verb == "qCurveTo" and points[-1] is None:
            # A contour without an on-curve point: one is implied between each pair of its
            # control points, the first between the last control point and the first.
            run = list(points[:-1])
            for index, control in enumerate(run):
                following = run[(index + 1) % len(run)]
                on = ((control[0] + following[0]) / 2, (control[1] + following[1]) / 2)
                current.append(("Q", (control, on)))
            start = current[-1][1][-1] if current else None
        elif verb == "qCurveTo":
            # A TrueType run of control points implies an on-curve point between each pair.
            run = list(points)
            if len(run) == 2:
                current.append(("Q", (run[0], run[1])))
            else:
                for index in range(len(run) - 1):
                    control, following = run[index], run[index + 1]
                    on = (
                        following
                        if index == len(run) - 2
                        else ((control[0] + following[0]) / 2, (control[1] + following[1]) / 2)
                    )
                    current.append(("Q", (control, on)))
        elif verb in ("closePath", "endPath") and start is not None:
            if current and current[-1][1][-1] != start:
                current.append(("L", (start,)))
    return [contour for contour in contours if len(contour) > 1]


def _point(value: Sequence[float]) -> list[float | int]:
    """Units, rounded to a thousandth and kept integral where they are."""
    out: list[float | int] = []
    for raw in value:
        number = round(float(raw), 3)
        out.append(int(number) if number == int(number) else number)
    return out


def commands_of(path: Path) -> list[list[Command]]:
    """A shape as contours of pen commands, in one rotation per contour: each is written from its
    leftmost point, the lowest of them where several share a column, and the contours are sorted,
    so the same outline reads the same way however the boolean operations walked it."""
    contours = []
    for segments in segments_of(path):
        ends = [segment[1][-1] for segment in segments]
        pivot = min(range(len(ends)), key=lambda i: (round(ends[i][0], 3), round(ends[i][1], 3)))
        ordered = segments[pivot + 1 :] + segments[: pivot + 1]
        commands: list[Command] = [["M", *_point(ends[pivot])]]
        for op, points in ordered:
            commands.append([op, *[value for p in points for value in _point(p)]])
        # The closing segment lands back on the start, which "Z" already says.
        if commands[-1][0] == "L" and commands[-1][1:] == commands[0][1:]:
            commands.pop()
        commands.append(["Z"])
        if len(commands) > 2:
            contours.append(commands)
    contours.sort()
    return contours


def piece_order(path: Path) -> tuple[Any, ...]:
    """A total order on pieces: where it sits, how big it is, what it draws."""
    return (
        *(round(value, 3) for value in path.bounds),
        round(abs(path.area), 3),
        [command for contour in commands_of(path) for command in contour],
    )


def rings_of(path: Path) -> list[list[tuple[float, float]]]:
    """A shape flattened to closed polylines, a curve taking one segment per `FLATTEN` units of
    its control polygon."""
    rings = []
    for segments in segments_of(path):
        here = segments[-1][1][-1]
        ring = [here]
        for op, points in segments:
            if op == "L":
                here = points[0]
                ring.append(here)
            else:
                control = [here, *points]
                length = sum(
                    abs(control[i + 1][0] - control[i][0]) + abs(control[i + 1][1] - control[i][1])
                    for i in range(len(control) - 1)
                )
                steps = max(2, int(length / FLATTEN) + 1)
                for step in range(1, steps + 1):
                    t = step / steps
                    working = list(control)
                    while len(working) > 1:
                        working = [
                            (
                                working[i][0] + (working[i + 1][0] - working[i][0]) * t,
                                working[i][1] + (working[i + 1][1] - working[i][1]) * t,
                            )
                            for i in range(len(working) - 1)
                        ]
                    ring.append(working[0])
                here = points[-1]
        if len(ring) > 3:
            rings.append(ring)
    return rings


def edges_of(path: Path) -> Array:
    """The flattened shape as an array of edges, one row `x0, y0, x1, y1` each."""
    rows = [
        (ring[index][0], ring[index][1], ring[index + 1][0], ring[index + 1][1])
        for ring in rings_of(path)
        for index in range(len(ring) - 1)
    ]
    return np.asarray(rows, dtype=np.float64).reshape(-1, 4)
