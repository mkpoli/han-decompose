"""The skeleton check: how far a cut's centre line runs from the centre line of its component
drawn alone, counting only what the cut adds.

Both shapes are stretched to a 128 × 128 grid and thinned to one-pixel lines (Zhang-Suen, no
pruning). The reading is the mean distance from each pixel of the cut's line to the nearest pixel
of the component's, in widths of the grid. It is one-sided on purpose: a cut that swallows a
neighbour grows a branch, and that is what the check charges for. A cut that misses part of its
component is the filled check's business.
"""

import numpy as np
import numpy.typing as npt

from .. import geometry as G
from . import filled

LIMIT = 0.0499
SIDE = 128
#: A stroke this grid can hold needs at most half as many peels; the rest is slack for a mask that
#: oscillates.
ROUNDS = 64

Mask = npt.NDArray[np.bool_]


def _neighbours(padded: Mask) -> list[Mask]:
    """P2..P9 of Zhang-Suen: N, NE, E, SE, S, SW, W, NW, each the size of the mask."""
    return [
        padded[:-2, 1:-1],
        padded[:-2, 2:],
        padded[1:-1, 2:],
        padded[2:, 2:],
        padded[2:, 1:-1],
        padded[2:, :-2],
        padded[1:-1, :-2],
        padded[:-2, :-2],
    ]


def _pass(mask: Mask, step: int) -> Mask:
    """One Zhang-Suen sub-iteration: the pixels to delete."""
    padded = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=bool)
    padded[1:-1, 1:-1] = mask
    p = _neighbours(padded)
    count = sum(n.astype(np.uint8) for n in p)
    ring = [*p, p[0]]
    transitions = sum((~ring[i] & ring[i + 1]).astype(np.uint8) for i in range(8))
    keep = mask & (count >= 2) & (count <= 6) & (transitions == 1)
    if step == 0:
        thinnable = ~(p[0] & p[2] & p[4]) & ~(p[2] & p[4] & p[6])
    else:
        thinnable = ~(p[0] & p[2] & p[6]) & ~(p[0] & p[4] & p[6])
    out: Mask = keep & thinnable
    return out


def thin(mask: Mask) -> Mask:
    """Zhang-Suen thinning of a mask to a one-pixel centre line."""
    current = mask
    for _ in range(ROUNDS):
        changed = False
        for step in (0, 1):
            doomed = _pass(current, step)
            if doomed.any():
                current = current & ~doomed
                changed = True
        if not changed:
            break
    return current


def line(ink: G.Path) -> G.Array:
    """The centre line of a shape, as the centres of its pixels in widths of the grid."""
    mask = filled.raster(filled.rings(G.commands_of(ink)), SIDE) > 0.5
    lines = thin(mask)
    ys, xs = np.nonzero(lines)
    return np.column_stack([(xs + 0.5) / SIDE, (ys + 0.5) / SIDE])


def away(cut: G.Array, reference: G.Array) -> float:
    """The mean distance from each point of the cut's line to the nearest point of the
    reference's."""
    if len(cut) == 0 or len(reference) == 0:
        return float("nan")
    distances = np.sqrt(((cut[:, None, :] - reference[None, :, :]) ** 2).sum(axis=2))
    return float(np.nanmean(distances.min(axis=1)))
