# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["fonttools[woff]==4.63.0", "brotli==1.2.0", "skia-pathops==0.9.2",
#                 "numpy==2.1.3"]
# ///
"""Hold data/mountain-instances.json.gz to what it claims.

The survey is only worth reading if each claim in it can be checked against the
font it came from. So every entry is redrawn here from the pinned faces and the
recorded ink is weighed against it:

  * the instances and the rest of the glyph tile the ink — together they are the
    glyph the font draws, and no two of them overlap;
  * each instance is the face's own outline, not a redrawing: its ink is a
    subset of the glyph's;
  * the three strokes come from one notch-pair neck cut and tile the instance;
  * the path down to each 山 agrees with the description it was cut from, and
    the component chain is what the operands walked through say it is;
  * every character attempted is either an entry or a skip with a reason.

    uv run scripts/check_mountain_instances.py

Says what failed and exits non-zero, or says the count of what held.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import pathops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_donor_parts as base  # noqa: E402
import build_mountain_instances as mountain  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "mountain-instances.json.gz"

# Ink this much smaller than the glyph's own is a rounding artefact of the
# boolean operations, not a piece of one element standing on another's.
SLACK = 0.002


def path_of(contours) -> pathops.Path:
    """A recorded path — contours of ["M"|"L"|"Q"|"C"|"Z", …numbers] — redrawn."""
    path = pathops.Path()
    pen = path.getPen()
    for contour in contours:
        for verb, *values in contour:
            if verb == "M":
                pen.moveTo(tuple(values))
            elif verb == "L":
                pen.lineTo(tuple(values))
            elif verb == "Q":
                pen.qCurveTo(tuple(values[:2]), tuple(values[2:]))
            elif verb == "C":
                pen.curveTo(tuple(values[:2]), tuple(values[2:4]), tuple(values[4:]))
            elif verb == "Z":
                pen.closePath()
    # A piece with counters is several contours, and the boolean operations read
    # a path's inside from its winding only once it has been resolved.
    path.simplify()
    return path


def area(path: pathops.Path) -> float:
    return abs(path.area)


def overlap(left: pathops.Path, right: pathops.Path) -> float:
    builder = pathops.OpBuilder(left)
    builder.add(right, pathops.PathOp.INTERSECTION)
    return area(builder.resolve())


def entry_faults(entry: dict, faces: dict[str, base.Face]) -> list[str]:
    """Everything one entry claims that its face does not bear out."""
    faults = []
    face = faces.get(entry["face"])
    if face is None:
        return [f"{entry['char']}: drawn by {entry['face']}, which is not a pinned face"]
    glyph = face.outline(entry["char"])
    if glyph is None:
        return [f"{entry['char']}: {entry['face']} draws no glyph for it"]

    parts = [path_of(instance["path"]) for instance in entry["instances"]]
    parts += [path_of(piece) for piece in entry["rest"]]
    whole = area(glyph)
    # The pieces tile the ink: none covers another's, each lies inside the glyph,
    # and together they come to exactly what the glyph draws. Said by adding the
    # areas rather than by taking their union, because a union has to decide what
    # is inside a piece that encloses counters, and that is the thing under test.
    together = sum(area(part) for part in parts)
    if abs(together - whole) > SLACK * max(whole, 1):
        faults.append(f"{entry['char']}: the instances and the rest come to "
                      f"{together:.0f} units², the glyph to {whole:.0f}")
    for at, one in enumerate(parts):
        for other in parts[at + 1:]:
            if overlap(one, other) > SLACK * max(whole, 1):
                faults.append(f"{entry['char']}: two of its pieces cover the same ink")
                break
        else:
            continue
        break

    for instance in entry["instances"]:
        ink = path_of(instance["path"])
        outside = pathops.OpBuilder(ink)
        outside.add(glyph, pathops.PathOp.DIFFERENCE)
        if area(outside.resolve()) > SLACK * max(whole, 1):
            faults.append(f"{entry['char']}: an instance draws ink the glyph does not")
        if abs(area(ink) - instance["area"]) > SLACK * max(instance["area"], 1):
            faults.append(f"{entry['char']}: an instance's recorded area is not its ink's")
        if instance["level"] != len(instance["through"]) + 1:
            faults.append(f"{entry['char']}: level {instance['level']} with "
                          f"{len(instance['through'])} components crossed")
        if instance["depth"] != len(instance["route"]):
            faults.append(f"{entry['char']}: depth {instance['depth']} with "
                          f"{len(instance['route'])} operands walked")
        if not instance["route"]:
            faults.append(f"{entry['char']}: an instance has no path down to it")
            continue
        last = instance["route"][-1]
        if (last["operator"], last["operand"]) != (instance["operator"], instance["operand"]):
            faults.append(f"{entry['char']}: the last step down is not the operand recorded")
        crossed = [step["inside"] for step in instance["route"] if step.get("inside")]
        if crossed != instance["through"]:
            faults.append(f"{entry['char']}: the components crossed do not match the path down")
        strokes = instance.get("strokes") or []
        if instance.get("strokeCount") != len(strokes):
            faults.append(f"{entry['char']}: the stroke count is not the strokes recorded")
        if strokes:
            tiling = instance.get("tiling")
            if not tiling:
                faults.append(f"{entry['char']}: strokes with no record of how they tile")
            elif (abs(tiling["area"] - 1) > 0.01 or tiling["overlap"] > 0.01
                  or tiling["outside"] > 0.01):
                faults.append(f"{entry['char']}: the strokes do not tile the instance "
                              f"({tiling})")
    return faults


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=TARGET)
    parser.add_argument("--cache", type=Path, default=ROOT / "cache")
    parser.add_argument("--limit", type=int, help="check only the first so many entries")
    args = parser.parse_args()

    with gzip.open(args.file, "rt", encoding="utf-8") as source:
        document = json.load(source)
    faces = {face.name: face for face in
             base.load_faces([], args.cache, False, mountain.FACE_FILES)}

    faults = []
    if document["attempted"] != len(document["entries"]) + len(document["skipped"]):
        faults.append(f"{document['attempted']} characters attempted, but "
                      f"{len(document['entries'])} entries and "
                      f"{len(document['skipped'])} skips")
    for row in document["skipped"]:
        if not row.get("reason"):
            faults.append(f"{row['char']}: skipped with no reason")

    table, labels = base.read_table(), base.read_labels()
    chosen = {char for char, _ in mountain.selection(table, labels)}
    covered = {entry["char"] for entry in document["entries"]}
    covered |= {row["char"] for row in document["skipped"]}
    if chosen != covered and not args.limit:
        faults.append(f"{len(chosen - covered)} characters that reach 山 went unattempted, "
                      f"{len(covered - chosen)} attempted that do not")

    entries = document["entries"][: args.limit] if args.limit else document["entries"]
    for at, entry in enumerate(entries, 1):
        faults.extend(entry_faults(entry, faces))
        print(f"\r{at}/{len(entries)} checked … {entry['char']}",
              end="", file=sys.stderr, flush=True)
    print("\r" + " " * 48, end="\r", file=sys.stderr)

    instances = sum(len(entry["instances"]) for entry in entries)
    if faults:
        print(f"{len(faults)} faults in {len(entries)} entries:")
        for fault in faults[:40]:
            print(f"  {fault}")
        return 1
    print(f"{len(entries)} entries, {instances} instances: the pieces tile each glyph, "
          f"every instance is the face's own ink, the strokes tile every instance, "
          f"and every path down agrees with its description.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
