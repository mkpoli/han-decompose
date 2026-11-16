"""Split each donor part of the review page into strokes along its junction lines.

Reads demo/donor-parts-review.json and writes it back with two splits of the
same ink:

* `geomStrokes` — one cut per part, along the junction line inside it.
* `strokeSeq` — the cut repeated until nothing cuts cleanly any more, in the
  order the IDS recursion reads, named after the recursion's own nodes where
  the cut and the description agree.

Every cut is a path intersection against a half plane, so the pieces keep the
part's own curves and their union is the part again.

Run with: uv run --with skia-pathops==0.9.2 python scripts/split_donor_strokes.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path as FsPath

import pathops

JSON_PATH = FsPath(__file__).resolve().parents[1] / "demo" / "donor-parts-review.json"

BIG = 10_000.0
FLAT = 1.5  # a segment this close to level counts as a horizontal edge
MIN_EDGE = 20.0  # and this long
EPS_AREA = 60.0  # ink smaller than this is a rounding artefact


def flatten_commands(raw):
    """The JSON stores a command list, a contour list, or a single command."""
    if isinstance(raw[0], str):
        return [raw]
    if isinstance(raw[0][0], str):
        return list(raw)
    out = []
    for contour in raw:
        out.extend(flatten_commands(contour))
    return out


def to_path(commands) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    open_contour = False
    for cmd in commands:
        op, nums = cmd[0], [float(n) for n in cmd[1:]]
        points = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
        if op == "M":
            if open_contour:
                pen.closePath()
            pen.moveTo(points[0])
            open_contour = True
        elif op == "L":
            pen.lineTo(points[0])
        elif op == "Q":
            pen.qCurveTo(*points)
        elif op == "C":
            pen.curveTo(*points)
        elif op == "Z":
            pen.closePath()
            open_contour = False
        else:
            raise ValueError(f"unknown path op {op!r}")
    if open_contour:
        pen.closePath()
    path.simplify()
    return path


def to_commands(path: pathops.Path):
    """Back to the JSON shape, as a list of contours."""
    contours = []
    current = None
    for verb, points in path.segments:
        if verb == "moveTo":
            current = [["M", *rounded(points[0])]]
            contours.append(current)
        elif current is None:
            continue
        elif verb == "lineTo":
            current.append(["L", *rounded(points[0])])
        elif verb == "curveTo":
            current.append(["C", *[v for point in points for v in rounded(point)]])
        elif verb == "qCurveTo":
            # A TrueType run of control points implies an on-curve point between each pair.
            for a, b in quad_runs(points):
                current.append(["Q", *rounded(a), *rounded(b)])
        elif verb in ("closePath", "endPath"):
            current.append(["Z"])
    return [c for c in contours if len(c) > 1]


def rounded(point):
    return [round(float(v), 3) for v in point]


def quad_runs(points):
    """Yield (control, on-curve) pairs for one qCurveTo, splitting implied points."""
    if len(points) == 2:
        yield points[0], points[1]
        return
    for i in range(len(points) - 1):
        control = points[i]
        nxt = points[i + 1]
        on = nxt if i == len(points) - 2 else ((control[0] + nxt[0]) / 2, (control[1] + nxt[1]) / 2)
        yield control, on


def rect(x0, y0, x1, y1) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((x0, y0))
    pen.lineTo((x1, y0))
    pen.lineTo((x1, y1))
    pen.lineTo((x0, y1))
    pen.closePath()
    return path


def clip(path: pathops.Path, box: pathops.Path) -> pathops.Path:
    out = pathops.op(path, box, pathops.PathOp.INTERSECTION)
    out.simplify()
    return out


def merge(paths) -> pathops.Path:
    out = pathops.Path()
    builder = pathops.OpBuilder()
    for p in paths:
        builder.add(p, pathops.PathOp.UNION)
    out = builder.resolve()
    out.simplify()
    return out


def contour_paths(path: pathops.Path):
    return list(path.contours)


def components(path: pathops.Path):
    """Split a path into connected pieces: one per outer contour, holes kept.

    A piece is cut back out of the path by intersecting with its own outer
    boundary, so counters (日's window) stay counters instead of filling in.
    """
    outers = [c for c in contour_paths(path) if c.area >= EPS_AREA]
    if not outers:  # all contours wound the other way
        outers = [c for c in contour_paths(path) if abs(c.area) >= EPS_AREA]
    result = []
    for outer in outers:
        piece = clip(path, outer)
        if abs(piece.area) >= EPS_AREA:
            result.append(piece)
    result.sort(key=lambda p: p.bounds[0])
    return result


def horizontal_lines(commands):
    """y values of the part's level edges — the lines a crossbar could be cut along."""
    ys = set()
    pen_x = pen_y = None
    start = None
    for cmd in commands:
        op, nums = cmd[0], [float(n) for n in cmd[1:]]
        if op == "M":
            pen_x, pen_y = nums[0], nums[1]
            start = (pen_x, pen_y)
            continue
        if op == "Z":
            if start is not None and pen_y is not None:
                if abs(start[1] - pen_y) < FLAT and abs(start[0] - pen_x) > MIN_EDGE:
                    ys.add(round((start[1] + pen_y) / 2, 3))
            continue
        x, y = nums[-2], nums[-1]
        if op == "L" and abs(y - pen_y) < FLAT and abs(x - pen_x) > MIN_EDGE:
            ys.add(round((y + pen_y) / 2, 3))
        pen_x, pen_y = x, y
    return sorted(ys)


def band_width(path: pathops.Path, y0, y1):
    """Total ink width in a thin horizontal band — how wide the stroke is there."""
    band = clip(path, rect(-BIG, y0, BIG, y1))
    height = max(y1 - y0, 1e-6)
    return abs(band.area) / height


@dataclass
class Split:
    strokes: list
    how: str
    roles: list


def split_part(commands) -> Split | None:
    path = to_path(commands)
    x0, y0, x1, y1 = path.bounds
    width, height = x1 - x0, y1 - y0
    if width <= 0 or height <= 0:
        return None
    for t in horizontal_lines(commands):
        if not (y0 + FLAT < t < y1 - FLAT):
            continue
        above = clip(path, rect(-BIG, t, BIG, BIG))
        below = clip(path, rect(-BIG, -BIG, BIG, t))
        up, down = components(above), components(below)
        if len(down) != 1:
            continue
        bar = down[0]
        bx0, by0, bx1, by1 = bar.bounds
        if bx1 - bx0 < 0.5 * width or by1 - by0 > 0.5 * height:
            continue  # the lower piece is not a crossbar

        if len(up) >= 2:
            # A bar carrying several uprights: the ones at its ends turn the same
            # corner as the bar (山's 凵), the inner ones are separate strokes (丨).
            tol = max(2.0, 0.04 * width)
            ends, inner = [], []
            for piece in up:
                px0, _, px1, _ = piece.bounds
                (ends if px0 <= bx0 + tol or px1 >= bx1 - tol else inner).append(piece)
            if not inner:
                continue
            base = merge([bar] + ends)
            return Split([base] + inner, "bar with ends, uprights cut free",
                         ["base"] + ["upright"] * len(inner))

        if len(up) == 1:
            # A wide bar hanging off a narrow neck: the bar is its own stroke (彐's 一).
            neck = band_width(path, t, t + min(12.0, (y1 - t) / 4))
            if (bx1 - bx0) >= 0.6 * width and (by1 - by0) <= 0.3 * height and neck <= 0.45 * (bx1 - bx0):
                return Split([up[0], bar], "base bar cut from the body", ["body", "一"])
    return None


def name_strokes(leaf, split: Split):
    """Name the pieces where the shape is one we recognise; otherwise number them."""
    plain = leaf.split(" ")[-1]
    count = len(split.strokes)
    if plain in ("山", "山上") and count == 2:
        return ["凵", "丨"]
    if plain == "彐" and count == 2:
        return ["ユ", "一"]
    return list(split.roles[:count])


def check(commands, split: Split):
    """The strokes must tile the part: same area, no overlap."""
    whole = to_path(commands)
    union = merge(split.strokes)
    if abs(abs(union.area) - abs(whole.area)) > 2.0:
        return f"area {abs(union.area):.1f} vs {abs(whole.area):.1f}"
    for i, a in enumerate(split.strokes):
        for b in split.strokes[i + 1 :]:
            if abs(clip(a, b).area) > EPS_AREA:
                return "strokes overlap"
    return None


# ---------------------------------------------------------------- deep split
#
# The same cut, repeated. One pass looks for a line the outline already runs
# along where the ink width steps — the boundary between a bar and what hangs
# off it — cuts the piece there, and recurses into both sides. The IDS
# recursion rides along: when a piece cuts into as many parts as the
# description gives that node children, the children name them and guide the
# next pass; otherwise the geometry carries on alone under the nearest name.

MIN_PIECE = 2400.0  # a piece smaller than this is a sliver, not a stroke
MIN_SPLIT = 9000.0  # ink smaller than this is one stroke already
STEP = 1.9  # the ink must get this much wider across the line to count as a junction
PROBE = 10.0  # how far either side of the line the width is measured
MAX_DEPTH = 7
# Shapes whose pieces have names of their own, by piece count.
KNOWN = {("山", 2): ["凵", "丨"], ("彐", 2): ["ユ", "一"], ("凵", 2): ["丨", "𠃊"]}


def plain(leaf):
    """`{42} 彐` names the component 彐; a bare `{47}` has no glyph to show."""
    return leaf.split(" ")[-1] if leaf else ""


def flat_commands(path: pathops.Path):
    return [cmd for contour in to_commands(path) for cmd in contour]


def level_edges(commands, axis):
    """Coordinates on `axis` where the outline runs flat — the lines to cut along."""
    other = 1 - axis
    values = set()
    pen = None
    start = None
    for cmd in commands:
        nums = [float(n) for n in cmd[1:]]
        if cmd[0] == "M":
            pen = start = (nums[0], nums[1])
            continue
        if cmd[0] == "Z":
            if start and pen and abs(start[axis] - pen[axis]) < FLAT and abs(start[other] - pen[other]) > MIN_EDGE:
                values.add(round((start[axis] + pen[axis]) / 2, 3))
            continue
        point = (nums[-2], nums[-1])
        if cmd[0] == "L" and abs(point[axis] - pen[axis]) < FLAT and abs(point[other] - pen[other]) > MIN_EDGE:
            values.add(round((point[axis] + pen[axis]) / 2, 3))
        pen = point
    return sorted(values)


def half(axis, lo, hi) -> pathops.Path:
    """The slab lo..hi along `axis`, unbounded across it."""
    return rect(lo, -BIG, hi, BIG) if axis == 0 else rect(-BIG, lo, BIG, hi)


def slab_width(path: pathops.Path, axis, lo, hi):
    """How wide the ink is inside a thin slab: its area over the slab's depth."""
    return abs(clip(path, half(axis, lo, hi)).area) / max(hi - lo, 1e-6)


def reading_order(paths):
    """Top before bottom, left before right, as a description reads."""
    if not paths:
        return []
    top = max(p.bounds[3] for p in paths)
    bottom = min(p.bounds[1] for p in paths)
    band = max(0.08 * (top - bottom), 12.0)
    return sorted(paths, key=lambda p: (round((top - p.bounds[3]) / band), p.bounds[0]))


@dataclass
class Cut:
    groups: list  # the pieces, in the order a description reads them
    how: str


def extent(path: pathops.Path, axis):
    return path.bounds[axis + 2] - path.bounds[axis]


def bar_cut(path: pathops.Path, axis, t, near, far) -> Cut | None:
    """A bar along the line with uprights off it: 山's 凵 plus 丨, 彐's body plus 一.

    `near` is the side the bar is on, `far` the side the uprights are on. The
    uprights that turn the bar's own corners stay with it; the inner ones come
    free as strokes of their own.
    """
    across = 1 - axis  # the bar runs across the cut line
    span, depth = extent(path, across), extent(path, axis)
    bars = components(near)
    if len(bars) != 1:
        return None
    bar = bars[0]
    if extent(bar, across) < 0.5 * span or extent(bar, axis) > 0.5 * depth:
        return None  # the near side is not a bar
    uprights = reading_order(components(far))
    if len(uprights) >= 2:
        tol = max(2.0, 0.04 * span)
        ends, inner = [], []
        for piece in uprights:
            at_end = piece.bounds[across] <= bar.bounds[across] + tol or \
                piece.bounds[across + 2] >= bar.bounds[across + 2] - tol
            (ends if at_end else inner).append(piece)
        if not inner:
            return None
        return Cut([merge([bar] + ends)] + inner,
                   "bar with its end uprights, the inner ones cut free")
    if len(uprights) == 1:
        reach = min(12.0, depth / 4) * (1 if far.bounds[axis + 2] > t else -1)
        neck = slab_width(path, axis, *sorted((t, t + reach)))
        if extent(bar, across) >= 0.6 * span and extent(bar, axis) <= 0.3 * depth \
                and neck <= 0.45 * extent(bar, across):
            return Cut(reading_order([bar, uprights[0]]), "the bar cut off the body")
    return None


def cut_once(path: pathops.Path) -> Cut | None:
    """The one cleanest cut of this piece, or nothing if it is already a stroke."""
    commands = flat_commands(path)
    best = None
    for axis in (1, 0):
        lo, hi = path.bounds[axis], path.bounds[2 + axis]
        for t in level_edges(commands, axis):
            if not lo + FLAT < t < hi - FLAT:
                continue
            under = clip(path, half(axis, -BIG, t))
            over = clip(path, half(axis, t, BIG))
            if abs(under.area) < MIN_PIECE or abs(over.area) < MIN_PIECE:
                continue
            thin = slab_width(path, axis, t - min(PROBE, t - lo), t)
            thick = slab_width(path, axis, t, t + min(PROBE, hi - t))
            if min(thin, thick) <= 0:
                continue
            step = max(thin, thick) / min(thin, thick)
            if step < STEP:
                continue
            near, far = (under, over) if thick < thin else (over, under)
            bar = bar_cut(path, axis, t, near, far)
            if bar:
                return bar
            # No bar to read, but the ink still steps across the line: cut there
            # and let the pieces be whatever the description calls them.
            groups = reading_order(components(under) + components(over))
            if len(groups) >= 2 and (best is None or step > best[0]):
                best = (step, Cut(groups, "cut where the ink steps"))
    return best[1] if best else None


@dataclass
class Piece:
    path: pathops.Path
    name: str
    whole: bool


def expand(path: pathops.Path, node, name, depth=0) -> list:
    """Cut `path` down to strokes, naming them from `node`'s children where they agree."""
    children = node["children"] if node else []
    cut = cut_once(path) if depth < MAX_DEPTH and abs(path.area) >= MIN_SPLIT else None
    if cut is None:
        # Nothing cuts cleanly. The piece stays whole; if the description asked
        # for a split here, that is worth saying.
        return [Piece(path, name, bool(children))]
    if children and len(children) == len(cut.groups):
        return [piece for group, child in zip(cut.groups, children)
                for piece in expand(group, child, plain(child["leaf"]) or name, depth + 1)]
    names = KNOWN.get((name, len(cut.groups))) or [name] * len(cut.groups)
    return [piece for group, label in zip(cut.groups, names)
            for piece in expand(group, None, label, depth + 1)]


def part_groups(entry):
    """The parts of one description element, in description order.

    A leaf drawn in several pieces (鳥 in five) is one element, so a run of
    parts under one name lines up with one node of the recursion.
    """
    groups = []
    for part in entry["parts"]:
        if groups and groups[-1]["leaf"] == part["leaf"]:
            groups[-1]["parts"].append(part)
        else:
            groups.append({"leaf": part["leaf"], "parts": [part]})
    return groups


def numbered(pieces):
    """Tell repeats apart: 鳥 in five pieces reads 鳥 1 … 鳥 5."""
    counts = {}
    for piece in pieces:
        counts[piece.name] = counts.get(piece.name, 0) + 1
    seen = {}
    out = []
    for piece in pieces:
        if counts[piece.name] > 1:
            seen[piece.name] = seen.get(piece.name, 0) + 1
            out.append(f"{piece.name} {seen[piece.name]}" if piece.name else f"{seen[piece.name]}")
        else:
            out.append(piece.name or "?")
    return out


def stroke_sequence(entry):
    """Every part of the entry cut to strokes, in the order the recursion reads."""
    groups = part_groups(entry)
    nodes = entry.get("recursive") or []
    aligned = nodes if len(nodes) == len(groups) else [None] * len(groups)
    sequence = []
    for group, node in zip(groups, aligned):
        name = plain(group["leaf"])
        paths = [to_path(flatten_commands(part["path"])) for part in group["parts"]]
        children = node["children"] if node else []
        if len(paths) == 1:
            pieces = expand(paths[0], node, name)
        elif children and len(children) == len(paths):
            # The element is drawn in as many pieces as the description gives it
            # children: each piece is that child.
            pieces = [piece for path, child in zip(reading_order(paths), children)
                      for piece in expand(path, child, plain(child["leaf"]) or name)]
        else:
            # Several pieces the description does not line up with: cut each on
            # its own geometry, under the element's name.
            pieces = [piece for path in reading_order(paths) for piece in expand(path, None, name)]
        labels = numbered(pieces)
        for piece, label in zip(pieces, labels):
            sequence.append({"leaf": group["leaf"], "stroke": label, "whole": piece.whole,
                             "path": to_commands(piece.path)})
    return sequence, groups


def verify_sequence(entry, sequence):
    """The strokes must tile the glyph: same area as the parts, no overlap, no NaN."""
    for stroke in sequence:
        for command in [c for contour in stroke["path"] for c in contour]:
            for value in command[1:]:
                if value != value or abs(value) > 1e6:
                    return f"bad coordinate {value!r} in {stroke['stroke']}"
    whole = merge([to_path(flatten_commands(part["path"])) for part in entry["parts"]])
    pieces = [to_path([c for contour in stroke["path"] for c in contour]) for stroke in sequence]
    if not pieces:
        return "no strokes"
    union = merge(pieces)
    if abs(abs(union.area) - abs(whole.area)) > 2.0:
        return f"union area {abs(union.area):.1f} vs glyph {abs(whole.area):.1f}"
    for i, a in enumerate(pieces):
        for b in pieces[i + 1:]:
            if abs(clip(a, b).area) > EPS_AREA:
                return "strokes overlap"
    return None


def main():
    data = json.loads(JSON_PATH.read_text())
    report = []
    for entry in data["entries"]:
        strokes = []
        for part in entry["parts"]:
            commands = flatten_commands(part["path"])
            split = split_part(commands)
            problem = check(commands, split) if split else None
            if split and not problem:
                names = name_strokes(part["leaf"], split)
                for name, piece in zip(names, split.strokes):
                    strokes.append({"leaf": part["leaf"], "stroke": name, "whole": False,
                                    "path": to_commands(piece)})
                report.append(f"{entry['char']} {part['leaf']}: {'+'.join(names)} ({split.how})")
            else:
                strokes.append({"leaf": part["leaf"], "stroke": part["leaf"].split(" ")[-1],
                                "whole": True, "path": to_commands(to_path(commands))})
                why = problem or "no junction line found"
                report.append(f"{entry['char']} {part['leaf']}: whole ({why})")
        entry["geomStrokes"] = strokes
        entry.pop("strokeParts", None)

        sequence, groups = stroke_sequence(entry)
        problem = verify_sequence(entry, sequence)
        if problem:
            raise SystemExit(f"{entry['char']}: stroke sequence does not tile the glyph — {problem}")
        entry["strokeSeq"] = sequence
        # The stroke figure draws our own ink, so KanjiVG's drawings are dead weight.
        entry.pop("kvgStrokes", None)
        entry.pop("leafStrokes", None)
        held = [stroke["stroke"] for stroke in sequence if stroke["whole"]]
        report.append(f"{entry['char']} strokes: {' · '.join(s['stroke'] for s in sequence)}"
                      f" ({len(sequence)} from {len(groups)} elements"
                      + (f", whole: {' '.join(held)}" if held else ", fully split") + ")")
    data.pop("kvgSource", None)
    data["generated"] = "layered donor split, strokes cut along junction lines"
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False) + "\n")
    print("\n".join(report), file=sys.stderr)


if __name__ == "__main__":
    main()
