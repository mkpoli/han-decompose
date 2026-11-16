# Licensing

The code is under the MIT licence (`LICENSE`). Data files are outside it.

Outlines are font software and keep their font's licence, in files that hold one font each. Every
other data file is label data under CC0-1.0. This page is a statement of how the project applies
those terms and no legal advice.

## Which terms reach which file

| File | Under |
|---|---|
| `outlines/<font>/…` | The font's licence, with the font's copyright line in the file. |
| `outlines/glyphwiki@…/…` | GlyphWiki's licence, with its address in the file. |
| `strokes/<font>/…` | The font's licence (GlyphWiki's for GlyphWiki). A stroke cut at a seam is new outline drawn from the font's, so it stays font data. |
| `cuts/<font>/…`, `drawn.tsv.gz`, `structures.tsv.gz`, `cuts.tsv.gz`, `skipped.tsv.gz`, `classes.tsv`, `components.tsv`, `library/…`, `forms/…`, `verdicts.tsv` | CC0-1.0. They hold contour indices, structures and labels, and no outline. |
| `packages/viewer/public/fonts/*.woff2` | Each subset under its font's licence, with the licence text beside it: Noto Sans CJK JP and Plangothic P1 under OFL-1.1, Jigmo under CC0-1.0. The Noto subset keeps no name with "Source". |
| `fonts.json`, `manifest.json` | CC0-1.0. `fonts.json` names each font's licence and copyright line. |

## Outline terms

[`pins/README.md`](../pins/README.md) gives each font with its version, digest, copyright line and
the place its terms are stated.

| Terms | Applies to | Asks |
|---|---|---|
| SIL Open Font License 1.1 (`OFL-1.1`) | Noto Sans CJK JP, Noto Serif CJK JP, Plangothic P1 and P2 | The copyright notice and the licence travel with every copy. Derived font data stays under the OFL and under no other licence. It is not sold by itself. A modified version does not use a Reserved Font Name: Noto Sans CJK JP reserves "Source". The authors' names do not promote a modified version. |
| Arphic Public License (`Arphic-1999`) | BabelStone Han PUA | The licence file travels unaltered with every copy (section 1). A modified file carries a prominent notice of how and when it was changed, and modifications are made freely available as a whole under the same licence (section 2). |
| GlyphWiki's data and article licence (`LicenseRef-GlyphWiki`) | Glyphs drawn from GlyphWiki's dump | Nothing: anyone may use, reproduce and redistribute the glyphs, modified or not, commercially or not, and naming the author is not required. GlyphWiki is credited all the same, with its address <https://glyphwiki.org/>. |

## How the project applies them

- **Label data.** How a character divides, which contours of a glyph form a component, and which
  shape a font draws are facts about characters and glyphs. The data states them in
  han-decompose's own notation and carries no text, attestation or field of the description tables
  the build tried candidates from. The terms of those tables (CHISE IDS under the GPL, Yi Bai's
  data under MIT, BabelStone's note that its data is facts) relicense one another along a chain and
  are not carried into the data. Those tables are cited as inputs in the docs.
- **KanjiVG.** A cut made along KanjiVG's stroke groups is a set of contours of the font; KanjiVG
  says which contours go together and none of its data is copied into the cut. Such cuts are label
  data under CC0-1.0 like every other label, and KanjiVG is cited in the docs.
- **BabelStone Han PUA.** Its glyph is the reference shape of a numbered component. Outlines taken
  from it stay under the Arphic Public License, in outline files of their own, each with a notice
  of how and when the font's data was changed and with the licence text in the release. The pinned
  font file is mirrored as an asset of this repository's releases, unaltered and beside the licence
  text, because its address upstream is replaced by each new version.
- **GlyphWiki.** Its glyphs are drawn from the dump with the KAGE engine and published as outline
  files under GlyphWiki's licence; the divisions and styles read from them are label data.
- **Reserved Font Name.** Release files are named by font identifier (`noto-sans-cjk-jp@2.004`).
  No file or product name here uses "Source".

## What is uncertain

- **GlyphWiki.** The licence was read in its English translation, archived on 2025-11-14
  (<https://web.archive.org/web/20251114152951/https://en.glyphwiki.org/wiki/GlyphWiki:License>);
  the page says the Japanese original governs, and that one did not load for an automated client
  on 2026-11-15.
- **Adobe-Japan1.** Only CID-to-character relations are taken from `aj17-kanji.txt`; the
  repository's permission notice is written for its README and the file states no terms of its
  own.
