# Stroke lab

Experiments in dividing a glyph's outline into its strokes, kept as they were run. They are the
starting point for the stroke layer below components and are not part of the package.

## `donor/` — eight ways to cut a donor glyph into strokes

From an `ids-input` worktree on `8916be817` (2026-11-07), run 2026-11-02.

| File | What it is |
|---|---|
| `lab_donor_strokes.py` | Runs eight methods on 25 donor glyphs and writes `donor-strokes-lab.json`: nearest centreline, skeleton, KanjiVG-shaped band, warp, notch-pair neck cut, neck watershed, hybrid, geodesic. |
| `cut_donor_strokes.py`, `split_donor_strokes.py` | The earlier single-method cutters the lab grew from. |
| `adopt_neck_cut.py` | Writes the neck cut's strokes back as the chosen result. |
| `donor-strokes-lab.html`, `donor-strokes-lab.json.gz` | The comparison page and its data. Unzip the data beside the page to view it. |
| `leaf-stroke-types.json`, `stroke-paths/` | Stroke types per leaf component and the KanjiVG-guided stroke paths drawn for review. |

Every method tiles the ink exactly by construction. The notch-pair neck cut gave the cleanest
strokes of the eight. None was clean enough to adopt: joins come out as rounded blobs and curves
lose their shape.

## `mountain/` — 山 in three strokes

From an `ids-input` worktree on `97724d4db` (2026-11-03).

| File | What it is |
|---|---|
| `split_mountain_strokes.py` | Neck-cuts each 山 instance into ㇑㇄㇑ along KanjiVG and writes `strokes` and `tiling` into the instance data. `STROKE_LAB` names the checkout holding the neck cut. |
| `build_mountain_instances.py`, `check_mountain_instances.py` | Build and check the 山 instance data (`data/mountain-instances.json.gz` in `ids-input`). |
| `split_wan.py` | The same for 萬's 山. |
| `build_donor_parts.diff` | The uncommitted change to `scripts/build_donor_parts.py` these scripts expect. |

All 2,220 instances in the data split into three strokes covering the ink once (area 1.0,
overlap 0).

## Elsewhere

The code that reached `main` in other repositories:

- han-compose `src/han_compose/kanjivg_cuts.py`: `Cutter.owners` and `groups` map each contour to the
  KanjiVG strokes whose centrelines run inside it, and mark contours two strokes share; `less` and
  `taken` remove a component or a stroke at contour grain.
- han-compose `js/src/strokes.js`: `splitStroke` lifts a stroke that owns all its contours.
- ids-input `docs/enclosure-graft.md` (#512): `graftTail` cuts a fused contour along a scanline at the
  same places in both masters.
