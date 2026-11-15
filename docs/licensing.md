# Licensing

The code is under the MIT licence (`LICENSE`). Data files are outside it.

A data file is under the licence of the font its outlines come from, and it lists the terms of the
description sources its labels were read from. This page says which terms reach which file and
what each asks. It is a statement of how the project applies them and no legal advice.

## Which terms reach which file

| File | Under | Lists |
|---|---|---|
| `outlines/<font>/…` | The font's licence, with the font's copyright line in the file. | — |
| `cuts/<font>/<source>/…` | The font's licence. The file holds contour indices and labels and no outline. | `terms.description`: the description source's terms. `terms.guide`: the guide's, on files with cuts made along a guide. `terms.notices`: the copyright and attribution lines. |
| `cuts.tsv.gz`, `skipped.tsv.gz` | Row by row, as the cut file the row comes from. | `licence_outline`, `licence_description`, `licence_guide` on each row. |
| `components.tsv` | Row by row, the terms of the source the row names. Rows drawn from the ids-input registry are GPL-2.0-or-later. | `source` on each row. |
| `fonts.json`, `sources.json` | MIT, as part of this repository. | Every font and source with its pin, licence and attribution. |

An outline file holds one font, and a cut file holds one font and one description source. The
flat tables gather the rows of every font and source.

## The terms in use

[`pins/README.md`](../pins/README.md) gives each font and source with its version, digest,
copyright line and the place its terms are stated.

| Terms | Applies to | Asks |
|---|---|---|
| SIL Open Font License 1.1 (`OFL-1.1`) | Noto Sans CJK JP, Noto Serif CJK JP, Plangothic P1 and P2 | The copyright notice and the licence travel with every copy. Derived font data stays under the OFL and under no other licence. It is not sold by itself. A modified version does not use a Reserved Font Name: Noto Sans CJK JP reserves "Source". The authors' names do not promote a modified version. |
| CC0 1.0 (`CC0-1.0`) | Jigmo, Jigmo2, Jigmo3 | Nothing. |
| Arphic Public License (`Arphic-1999`) | BabelStone Han PUA | The licence file travels unaltered with every copy. A modified file carries a prominent notice of how and when it was changed, and modifications are made freely available as a whole under the same licence. |
| Header note 2 of IDS.TXT (`LicenseRef-BabelStone-IDS`) | BabelStone IDS | Nothing: the maintainer holds IDS sequences to be facts outside copyright under U.S. law and waives claims to the file's presentation. It is credited all the same. |
| GNU GPL 2.0 or later (`GPL-2.0-or-later`) | CHISE IDS, the ids-input component registry | Copies and derived works stay under the GPL, with source available. |
| MIT (`MIT`) | Yi Bai's IDS data | The copyright notice and the permission notice travel with copies. |
| CC BY-SA 3.0 (`CC-BY-SA-3.0`) | KanjiVG | Attribution, and adaptations shared under the same licence. |
| GlyphWiki's data and article licence (`LicenseRef-GlyphWiki`) | GlyphWiki glyphs | Nothing, as ids-input's data notes summarise it: anyone may use, copy and modify the glyph data, without attribution. It is credited all the same. |
| Adobe's permission notice (`LicenseRef-Adobe-Japan1`) | `aj17-kanji.txt` | The notice travels with copies, and a derived work is not presented as a copy or version of the original. |

## What is uncertain

- **OFL outlines and GPL labels.** Whether a set of contour indices into an OFL font, labelled
  from a GPL description table, is a derived work of that table is unsettled. Outline files and
  cut files are separate, and cut files are separate per source, so a user can take the outlines
  with the labels of a public-domain or MIT source only.
- **Cuts made along KanjiVG's groups.** han-compose treats what it draws from such cuts as an
  adaptation of KanjiVG under CC BY-SA 3.0. If a cut's contour indices are an adaptation too,
  share-alike asks for CC BY-SA on them while the OFL allows no other licence on font data. A
  guided cut names the guide's licence (`licence.guide`), and no such cut is published until this
  is settled.
- **Flat tables.** `cuts.tsv.gz`, `skipped.tsv.gz` and `components.tsv` put rows under different
  terms side by side: GPL-2.0-or-later, MIT and public-domain descriptions. Whether such a table is
  a mere aggregate of its rows is unsettled. If it is not, the tables are split per source as the
  cut files are.
- **BabelStone IDS.** Its header says the data draws on Kawabata Taichi's IDS data, which descends
  from CHISE, and on IRG submissions. The maintainer's statement that the sequences are facts
  covers his file; the terms of what it draws on are not stated there.
- **Reserved Font Name.** Release files are named by font identifier (`noto-sans-cjk-jp@2.004`).
  No file or product name here uses "Source".
- **Adobe-Japan1.** The repository's permission notice is written for its README; `aj17-kanji.txt`
  states no terms of its own. Only CID-to-character relations are taken from it.
- **GlyphWiki.** Its licence page was not read directly; the terms above are a summary at second
  hand. Glyphs are compared with cuts and published only as reference outlines, named with the
  date they were fetched.
