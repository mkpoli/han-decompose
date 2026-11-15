# Reproduction of ids-input's cuts

The cutters came from ids-input. Each was first made to give what ids-input gave, on the same
fonts and the same descriptions, and only then changed. This page records how close each comes.

`uv run pytest -m reproduction` runs the surveys again and holds them against
`tests/fixtures/survey/`; it takes minutes and needs the pinned fonts and tables in the cache.

## Two grains

ids-input cuts along the outlines that are left once a glyph's overlapping contours are merged.
han-decompose writes a cut as contours of the font. The two agree wherever each merged outline is
drawn by contours of its own. They part where a font draws two components with one contour that
meets itself at a point: merging separates them there, and no set of whole contours can. Such
outlines are one piece here (`src/han_decompose/pieces.py`).

The code was run both ways: with pieces as merging leaves them, to show the port decides as
ids-input does, and as it is committed.

## Stacks on 山

ids-input `data/donor-parts.json`: the characters BabelStone describes as a stack standing on 山,
read in Noto Sans CJK JP, then Jigmo, Jigmo2 and Jigmo3.

| | Candidates | Closed |
|---|---|---|
| ids-input | 138 | 114 |
| han-decompose | 138 | 114 |

The same 114, each in the same font, with the same weakest agreement and the same number of
pieces per component (`tests/fixtures/stacks-on-shan.tsv`).

## Survey of 山

ids-input `data/mountain-instances.json.gz` (built 2026-11-03): every character whose BabelStone
description reaches 山, read in Noto Sans CJK JP, then Plangothic P1 and P2.

| | Attempted | Characters with a 山 | Instances | Refused by a gate |
|---|---|---|---|---|
| ids-input | 2,926 | 2,150 | 2,220 | 55 |
| han-decompose, pieces as merging leaves them | 2,926 | 2,150 | 2,220 | 55 |
| han-decompose | 2,926 | 2,141 | 2,209 | 58 |

At ids-input's grain every character has the same tree, the same depth and, for each instance, the
same likeness, filled reading and skeleton reading.

As committed, 2,126 characters are the same in all of that. The others:

- **23 lost.** 𡀢𡶞𡷁𡹐𡺚𡺸𡽓𡽤𡾜𡾢𢋬𢣆𤨉𥉴𦏦𧏢𩞉𩷘𪈡𪖾𪧄𫶎𱜌, all read in Plangothic P1. One contour
  runs through the 山 and a neighbour, so they are one piece: the glyph then has too few pieces,
  or the piece does not look like 山, or the checks refuse it.
- **14 gained.** 𠭏𠰛𡺧𡻔𡼳𡽑𡿍𧔮𪨻𪩏𭗉𭗵𮫻𱛴. ids-input skipped them because the union of their
  pieces came out smaller than the glyph, which is how it tests that the pieces are the whole
  glyph. Here the pieces' areas are summed, and they add up.
- **1 differs.** 𡻀 (⿰山峯) keeps the 山 it names and loses the one inside 峯, whose pieces share a
  contour.

Skipped here, by reason: 290 `too-few-pieces`, 193 `layout-mismatch`, 186 `unlike-element`,
49 `ambiguous`, 11 `no-reference-glyph`, 2 `no-enclosure`.

## Sources

- ids-input, branch `feat/donor-parts` at `97724d4db` with its uncommitted survey work:
  `scripts/build_donor_parts.py`, `scripts/build_mountain_instances.py`, `analysis/`,
  `data/donor-parts.json`, `data/mountain-instances.json.gz`.
- Fonts and tables as pinned in `pins/`.
