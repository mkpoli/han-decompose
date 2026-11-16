# Reproduction of ids-input's cuts

The cutters came from ids-input. Each was first made to give what ids-input gave, on the same
fonts and the same descriptions, and only then changed. This page records how close each comes.

`uv run pytest -m reproduction` runs the surveys again and holds them against
`tests/fixtures/survey/`; it takes minutes and needs the pinned fonts and tables in the cache.

## Cutting from the corpus

The tables below were first measured with BabelStone's or CHISE's first description of each
character. The cutters now read every character's canonical structures from ids-input's corpus
(`docs/format.md`, 2.6), the first structure of a character being the one the survey cuts, and the
reproduction tests compare the trees of ids-input's survey as structures: `⿰亻山` is `⿰人山`.
`expected.json` holds the characters and components that differ from ids-input's files. The
sections after this one record the earlier reading, in which the surveys used BabelStone's
descriptions alone and the lifts CHISE's.

Before components are compared with every member of their class, a glyph that draws 亻, 扌 or 氵
is compared with 人, 手 or 水, so the numbers in this section are lower than they will be once
classes are used.

| | Attempted | Characters with the component | Instances |
|---|---|---|---|
| 山, ids-input | 2,926 | 2,150 | 2,220 |
| 山, canonical structures | 3,114 | 2,146 | 2,217 |
| 口, ids-input | 26,446 | 4,731 | 5,033 |
| 口, canonical structures | 29,843 | 4,319 | 4,636 |

| | Entities | Library cuts |
|---|---|---|
| Sans forms, ids-input | 446 | 353 |
| Sans forms, canonical structures | 403 | 267 |

The characters that differ from ids-input's survey, by what differs:

- **Gained, 156 of 山 and 328 of 口.** Characters BabelStone does not describe, which the corpus
  does through CHISE and zi.tools (the whole of Extension I among them), and characters whose first
  structure now closes where BabelStone's did not.
- **Lost, 160 of 山 and 740 of 口.** A part that a glyph draws as 亻, 扌 or 氵 is compared with the
  canonical 人, 手 or 水 and falls under the floor of likeness (仙, 催, 汕); a character whose first
  structure in the corpus is another than BabelStone's (炭 is `⿸屵火` first); a chain that flattens
  into a three-way division the glyph's pieces do not follow.
- **Differ.** The same character read with the same instances at another depth, because a part
  that spells a character (`⿱山王`) is that character and is opened into its parts one level down,
  or with another tree, because the first structure of the corpus is not BabelStone's.

## Two grains

ids-input cuts along the outlines that are left once a glyph's overlapping contours are merged.
han-decompose writes a cut as contours of the font. The two agree wherever each merged outline is
drawn by contours of its own. They part where a font draws two components with one contour that
meets itself at a point: merging separates them there, and no set of whole contours can. Such
outlines are one piece here (`src/han_decompose/pieces.py`).

The code was run both ways: as it is committed, and once with two things patched back to
ids-input's to show the port decides as ids-input does. The patch left pieces as merging leaves
them, and tested that the pieces are the whole glyph by the area of their union where the code
sums their areas. It is no switch of the code.

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
| han-decompose, patched to ids-input's grain | 2,926 | 2,150 | 2,220 | 55 |
| han-decompose | 2,926 | 2,141 | 2,209 | 58 |

At ids-input's grain every character has the same tree, the same depth and, for each instance, the
same likeness, filled reading and skeleton reading.

As committed, 2,126 characters are the same in all of that. The others:

- **23 lost.** 𡀢𡶞𡷁𡹐𡺚𡺸𡽓𡽤𡾜𡾢𢋬𢣆𤨉𥉴𦏦𧏢𩞉𩷘𪈡𪖾𪧄𫶎𱜌, read in Plangothic P1 and, 𱜌, in P2. One contour
  runs through the 山 and a neighbour, so they are one piece: the glyph then has too few pieces,
  or the piece does not look like 山, or the checks refuse it.
- **14 gained.** 𠭏𠰛𡺧𡻔𡼳𡽑𡿍𧔮𪨻𪩏𭗉𭗵𮫻𱛴. ids-input skipped them because the union of their
  pieces came out smaller than the glyph, which is how it tests that the pieces are the whole
  glyph. Here the pieces' areas are summed, and they add up.
- **1 differs.** 𡻀 (⿰山峯) keeps the 山 it names and loses the one inside 峯, whose pieces share a
  contour.

Skipped here, by reason: 290 `too-few-pieces`, 193 `layout-mismatch`, 186 `unlike-element`,
49 `ambiguous`, 11 `no-reference-glyph`, 2 `no-enclosure`.

## Survey of 口

ids-input `data/component-instances-口.json.gz` (built 2026-11-09): the same survey for 口, with
the limits of 山 borrowed. No cut of 口 has been judged by eye, so how many of the refusals are
wrong is unknown, and every cut says `calibrated: false`.

| | Attempted | Characters with a 口 | Instances | Refused by a gate |
|---|---|---|---|---|
| ids-input | 26,446 | 4,731 | 5,033 | 4,626 |
| han-decompose, patched to ids-input's grain | 26,446 | 4,731 | 5,033 | 4,626 |
| han-decompose | 26,446 | 4,732 | 5,030 | 4,587 |

At ids-input's grain every character has the same tree, depth and scores.

As committed, 4,697 characters are the same in all of that. The others:

- **29 lost.** 𠮭𠱪𠻘𡀆𡄉𡞺𡬗𢣆𢸊𤜀𤺬𥰪𦳬𧁤𧨈𧰈𧰑𧰛𨿡𨿦𩁛𩟈𪉣𪢢𪯟𭉆𮇰𮟜𱊻. A contour runs through the 口 and a neighbour, or a
  piece's contours do not draw the piece alone.
- **30 gained.** 㐯㗢䛗䝂䨐咶嚚龛𠆆𠰯𠳡𠷰𠹃𠼩𡁝𧔁𧚱𨜢𪓪𪕡𪕲𫙻𫜝𫫐𬶔𭍈𮟺, which ids-input skipped because the union of their
  pieces lost area; 𫴜 and 𮝣, where it found two readings fitting equally well; and 𲄲, which it
  refused at the skeleton gate. In those three a joined piece changes the reading.
- **5 differ.** 𠵘𡀢𡁚𧜉𱄆: a component deeper in the tree no longer opens, so the reading settles one
  level up, or a joined piece changes the 口's scores.

Skipped here, by reason: 14,364 `too-few-pieces` (the glyph has fewer pieces than the tree has
leaves), 1,816 `layout-mismatch`, 1,480 `unlike-element`, 532 `ambiguous`, 121
`no-reference-glyph`, 10 `too-many-pieces`, 7 `no-enclosure`, 6 `does-not-tile`.

## Lifted components

han-compose `data/custom-forms.json.gz` (format 2), written by ids-input's
`scripts/build_custom_cuts.py`: the form of each CHISE entity and zi.tools chain that stands, and
its library of host cuts, in the `sans` chain (Noto Sans CJK JP, Plangothic P1 and P2) and the
`serif` chain (Noto Serif CJK JP, Jigmo2, Jigmo3, Jigmo). `tests/fixtures/lift/` holds it without
its outlines.

| | Sans: entities | chains | library cuts | Serif: entities | chains | library cuts |
|---|---|---|---|---|---|---|
| ids-input | 446 | 7 | 353 | 296 | 1 | 189 |
| han-decompose, patched to ids-input's grain | 446 | 7 | 353 | 296 | 1 | 189 |
| han-decompose | 444 | 7 | 352 | 296 | 1 | 188 |

At ids-input's grain every form comes from the same host with the same match, margin, agreement
and reference likeness, and every library has the same number of cuts in each place.

As committed, in the `sans` chain 444 of 453 forms are the same in all of that:

- **2 lost.** `&CDP-86AA;`, `&CDP-88D7;`: the host's component shares a contour with a
  part, or a piece's contours do not draw it alone.
- **7 differ.** `&AJ1-01445;`, `&AJ1-04449;`, `&CDP-8552;`, `&CDP-85D4;`, `&CDP-8DEB;`, `&MJ018170;`, `&U-i003+5915;`: the same host and match, with another margin
  or one host fewer agreeing, because a neighbouring group of pieces is now one piece.

In the `serif` chain all 297 forms stand and 296 are the same; `&CDP-8CEC;` has one host
fewer in its library.

Hosts read: 1,117 in `sans` and 620 in `serif`; hosts that gave nothing, each kept as a skipped
attempt with its reason: 2,726 and 3,223.

## Sources

- ids-input, branch `feat/donor-parts` at `97724d4db` with its uncommitted survey work as it
  stood on 2026-11-15 (the survey script was last changed on 2026-11-09, after the 口 file was
  written; the patched run gives both files as they are):
  `scripts/build_donor_parts.py`, `scripts/build_mountain_instances.py`, `analysis/`,
  `data/donor-parts.json`, `data/mountain-instances.json.gz`,
  `data/component-instances-口.json.gz`.
- ids-input `main`: `scripts/build_custom_cuts.py`; han-compose `main`: `data/custom-forms.json.gz`.
- Fonts and tables as pinned in `pins/`.
