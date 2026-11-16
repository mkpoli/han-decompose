# Glyph records of two han-compose exports

A few `G` records copied from web exports of han-compose (format 6), each cut down to its font,
its `v` flag and, per contour, the pen commands and the points at weight 400. The parity test
reads the same glyphs from the pinned fonts and requires the same contours.

| File | Export | han-compose commit |
|---|---|---|
| `sans.json` | `a83fc941166b-sans-compose-layout-v4-f6+variants` | `a83fc941166b` |
| `serif.json` | `8156f838798c-serif-compose-layout-v4-serif-f6+variants` | `8156f838798c` |

The records are outlines of the fonts they name and stay under those fonts' terms, which
[`pins/README.md`](../../../pins/README.md) gives with each copyright line: SIL OFL 1.1 for Noto
Sans CJK JP, Noto Serif CJK JP and Plangothic. han-compose, which wrote the
exports, is MIT, <https://github.com/mkpoli/han-compose>.
