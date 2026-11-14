# Golden files

One character, 催 (U+50AC), in the layout of a release, written by hand to pin the format. No
cutter produced them.

| File | Holds |
|---|---|
| `outlines/noto-sans-cjk-jp@2.004/050.json` | 催: 11 contours in 3 pieces. 偹 (U+5079), the skipped attempt's glyph: 11 contours in 2 pieces. |
| `cuts/noto-sans-cjk-jp@2.004/babelstone/050.json` | One reading of 催 as `⿰亻崔`, with 崔 opened into `⿱山隹`, and one skipped attempt, 偹. |
| `cuts.tsv`, `skipped.tsv` | The flat tables of that cut file. |

The JSON files are laid out for reading; a release writes the same values on one line with sorted
keys and compresses them.

## Sources

- Contours: Noto Sans CJK JP 2.004, variable font at `wght` 400,
  <https://github.com/notofonts/noto-cjk/raw/Sans2.004/Sans/Variable/TTF/NotoSansCJKjp-VF.ttf>,
  SHA-256 `240c9b83bf7b386edbae39995ae7e068ed4583f484d92e4a74c34158b5f27b1a`. © 2014-2021 Adobe
  (http://www.adobe.com/), with Reserved Font Name 'Source'. SIL Open Font License 1.1; the text
  is `OFL-NotoSansCJK.txt`, copied from the font's repository at tag `Sans2.004`.
- Descriptions: BabelStone IDS by Andrew West, File Date 2025-06-27,
  <https://www.babelstone.co.uk/CJK/IDS.TXT>. 催 is `⿰亻崔`, 崔 is `⿱山隹`, 偹 is `⿲亻丨备`. Its
  header (note 2) places the sequences in the public domain.
- Pieces and contour labels: assigned by hand from a drawing of the contours and the areas where
  two contours overlap.
