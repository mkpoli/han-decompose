# Parity with han-compose

han-compose addresses a cut as indices into the contours of the host glyph. Those indices mean the
same contours here only if both projects read a glyph the same way: the same font of the chain,
the same contours in the same order, the same pen commands and the same points.

`han-decompose parity <export> --design <id>…` checks that against a han-compose web export
(format 6), reading the glyphs in the fonts of the designs named in order (`source-han-sans`, `plangothic` by default). For every record of the export that holds a glyph, it reads the glyph from the pinned
fonts, brings the points from hundredths of a unit to the export's quarter units, and requires
equality with the record's weight-400 outline. It also requires that the export took the glyph
from the same font of the chain, that no glyph record is left without a selector that reaches
it, and that the folder holds as many shards and records as its manifest states. The command
exits 1 on any difference, on a folder that lost a shard, and on one without a glyph record.

Points are compared on the export's grid of a quarter unit. Two outlines that agree there can
differ by under a quarter unit in hundredths; the hundredths themselves have no second witness.

The export must have been written from the chain's own font files; its manifest records their
SHA-256, and an export of other files is refused.

## Results

Run on 2026-11-15 against the exports of han-compose commits `a83fc941166b` (sans) and
`8156f838798c` (serif), each with and without its added variation sequences.

Identical means equal at a quarter unit.

| Export | Chain | Glyph records | Identical | Different | From another font |
|---|---|---|---|---|---|
| `a83fc941166b-sans-compose-layout-v4-f6` | `sans` | 108,621 | 108,621 | 0 | 0 |
| `a83fc941166b-sans-compose-layout-v4-f6+variants` | `sans` | 110,089 | 110,089 | 0 | 0 |
| `8156f838798c-serif-compose-layout-v4-serif-f6` | `serif` | 108,583 | 108,583 | 0 | 0 |
| `8156f838798c-serif-compose-layout-v4-serif-f6+variants` | `serif` | 110,051 | 110,051 | 0 | 0 |

`tests/fixtures/composer-export/` keeps a few of those records, one or more per font of each
chain, so the same check runs as a unit test wherever the pinned fonts are in the cache.

## What it does not cover

- The heavy master of a variable font and the stroke widths a record carries: han-compose's own.
- Fonts with cubic outlines, and faces of a collection. None is pinned.
- Variation sequences a later font of the chain maps and the first does not. han-compose looks a
  sequence up in the first font only, so its exports hold no record for them: 14,953 of the
  29,740 sequences of the `serif` chain come from Jigmo, and one of the `sans` chain from
  Plangothic P1.
- Characters the exports hold no record for. The sans export holds a glyph record for 108,621 of
  the 149,849 selectors its chain maps.
