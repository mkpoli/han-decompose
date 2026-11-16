# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["numpy", "scipy", "shapely", "scikit-image", "pillow"]
# ///
"""Break every cut-out 山 into its three strokes along the ink's own notches.

The cut that does it is the notch-pair neck cut of scripts/lab_donor_strokes.py:
it finds the corners a glyph's outline turns inward at — which is what one brush
stroke leaves where another crosses it — joins the facing pairs with a straight
line, and gives each resulting piece whole to the stroke it lies under. That
script is in the variant-wan worktree and is imported from there, with KanjiVG's
three strokes of 山 as the guide to which piece is which.

山 is ㇑ ㇄ ㇑, so a sound cut returns three regions. The count is recorded for
every instance, and so is how exactly the regions tile the ink, because a cut
that fails returns the wrong number and that is the thing a reader should see.

    uv run scripts/split_mountain_strokes.py [--workers N] [--limit N]

Reads and rewrites data/mountain-instances.json.gz, adding `strokes` and
`strokeCount` to each instance.

Stroke data: KanjiVG (https://kanjivg.tagaini.net/), Ulrich Apel, CC BY-SA 3.0.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "mountain-instances.json.gz"
# The checkout holding the neck cut (lab/strokes/donor here). Its scripts/ is put on the
# path so the module loads with its KanjiVG store beside it, as it expects.
LAB = Path(os.environ["STROKE_LAB"])

MOUNTAIN = "山"
# KanjiVG writes a stroke's shape variants as a trailing letter: ㇑a is a ㇑.
VARIANT = re.compile(r"[a-z]+$")

_lab = None
_base = None
_guide = None


def machinery():
    """The neck cut, its shared tail, and KanjiVG's three strokes of 山."""
    global _lab, _base, _guide
    if _lab is None:
        sys.path.insert(0, str(LAB / "scripts"))
        import cut_donor_strokes
        import lab_donor_strokes

        _base, _lab = cut_donor_strokes, lab_donor_strokes
        _guide = _base.leaf_strokes(MOUNTAIN)
        if not _guide or len(_guide) != 3:
            raise SystemExit(f"KanjiVG draws {MOUNTAIN} in "
                             f"{len(_guide or [])} strokes, not three.")
    return _lab, _base, _guide


def shape_of(path, base):
    """A recorded path — a list of contours of commands — as a polygon."""
    return base.rings_to_polygon(base.flatten_part([c for contour in path for c in contour]))


def split(job: tuple[str, int, list]) -> tuple[str, int, dict]:
    """One instance's three strokes, or the reason it stayed whole."""
    char, index, path = job
    lab, base, guide = machinery()
    try:
        ink = shape_of(path, base)
        if ink is None or ink.is_empty:
            return char, index, {"strokes": [], "strokeCount": 0,
                                 "strokeNote": "the instance has no ink to cut"}
        canvas = lab.Canvas(ink, guide)
        regions = lab.finish(lab.label_neck_cut(canvas), canvas)
        tiling = lab.check(regions, ink)
        strokes = []
        for (kind, _), region in zip(guide, regions):
            if region is None or region.is_empty:
                continue
            contours = base.to_commands(region)
            if contours:
                strokes.append({"type": VARIANT.sub("", kind) or kind,
                                "kvgType": kind, "path": contours})
        return char, index, {
            "strokes": strokes,
            "strokeCount": len(strokes),
            # How well the strokes tile the 山: area 1 is exact, and overlap and
            # spill are fractions of its ink. A ragged cut shows up here.
            "tiling": {key: round(float(tiling[key]), 5) for key in
                       ("area", "overlap", "outside")},
        }
    except Exception as reason:  # a cut that cannot be made, named not guessed
        return char, index, {"strokes": [], "strokeCount": 0,
                             "strokeNote": f"{type(reason).__name__}: {reason}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=TARGET)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, help="split only the first so many instances")
    args = parser.parse_args()

    lab, _, guide = machinery()
    with gzip.open(args.file, "rt", encoding="utf-8") as source:
        document = json.load(source)

    jobs = [(entry["char"], index, instance["path"])
            for entry in document["entries"]
            for index, instance in enumerate(entry["instances"])]
    if args.limit:
        jobs = jobs[: args.limit]
    held = {(entry["char"], index): instance
            for entry in document["entries"]
            for index, instance in enumerate(entry["instances"])}

    counts: dict[int, int] = {}
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for char, index, result in pool.map(split, jobs, chunksize=8):
            held[(char, index)].update(result)
            counts[result["strokeCount"]] = counts.get(result["strokeCount"], 0) + 1
            done += 1
            print(f"\r{done}/{len(jobs)} split … {char}", end="", file=sys.stderr, flush=True)
    print("\r" + " " * 48, end="\r", file=sys.stderr)

    document["strokeMethod"] = (
        "notch-pair neck cut (scripts/lab_donor_strokes.py): the corners the outline turns "
        f"inward at are joined across the ink and each piece goes whole to the stroke it lies "
        f"under, on a {lab.RASTER} px raster, guided by KanjiVG's three strokes of {MOUNTAIN}"
    )
    document["strokeGuide"] = [VARIANT.sub("", kind) or kind for kind, _ in guide]
    document["kvgSource"] = "KanjiVG, Ulrich Apel, CC BY-SA 3.0, https://kanjivg.tagaini.net/"
    document["strokeCounts"] = {str(key): counts[key] for key in sorted(counts)}

    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
    with gzip.open(args.file, "wt", encoding="utf-8", compresslevel=9) as out:
        out.write(raw)
    print(f"{args.file.name}: {len(jobs)} instances split, "
          f"{args.file.stat().st_size:,} bytes gzipped from {len(raw):,}")
    for key in sorted(counts):
        print(f"  {counts[key]:5d} instances cut into {key} strokes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
