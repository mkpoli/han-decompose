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
| `cuts.<source>.tsv.gz`, `skipped.<source>.tsv.gz` | Row by row, as the cut file the row comes from. A table holds the rows of one description source. | `licence_outline`, `licence_description`, `licence_guide` on each row. |
| `components.<source>.tsv` | The terms of the source the table is named for. The table of the ids-input registry is GPL-2.0-or-later. | `source` on each row. |
| `fonts.json`, `sources.json` | MIT, as part of this repository. | Every font and source with its pin, licence and attribution. |

An outline file holds one font, and a cut file holds one font and one description source. A flat
table gathers the rows of every font under one description source.

## The terms in use

[`pins/README.md`](../pins/README.md) gives each font and source with its version, digest,
copyright line and the place its terms are stated.

| Terms | Applies to | Asks |
|---|---|---|
| SIL Open Font License 1.1 (`OFL-1.1`) | Noto Sans CJK JP, Noto Serif CJK JP, Plangothic P1 and P2 | The copyright notice and the licence travel with every copy. Derived font data stays under the OFL and under no other licence. It is not sold by itself. A modified version does not use a Reserved Font Name: Noto Sans CJK JP reserves "Source". The authors' names do not promote a modified version. |
| CC0 1.0 (`CC0-1.0`) | Jigmo, Jigmo2, Jigmo3 | Nothing. |
| Arphic Public License (`Arphic-1999`) | BabelStone Han PUA: the reference shape of a numbered component | The licence file travels unaltered with every copy (section 1). A modified file carries a prominent notice of how and when it was changed, and modifications are made freely available as a whole under the same licence (section 2). |
| Header note 2 of IDS.TXT (`LicenseRef-BabelStone-IDS`) | BabelStone IDS | Nothing: the maintainer holds IDS sequences to be facts outside copyright under U.S. law and waives claims to the file's presentation. It is credited all the same. |
| GNU GPL 2.0 or later (`GPL-2.0-or-later`) | CHISE IDS, the ids-input component registry | Copies and derived works stay under the GPL, with source available. |
| MIT (`MIT`) | Yi Bai's IDS data | The copyright notice and the permission notice travel with copies. |
| CC BY-SA 3.0 (`CC-BY-SA-3.0`) | KanjiVG, the guide of some cuts | Attribution, and adaptations shared under the same licence. |
| GlyphWiki's data and article licence (`LicenseRef-GlyphWiki`) | GlyphWiki glyphs, a check on cuts | Nothing: anyone may use, reproduce and redistribute the glyphs, modified or not, commercially or not, and naming the author is not required. GlyphWiki is credited all the same, with its address <https://glyphwiki.org/>. |
| Adobe's permission notice (`LicenseRef-Adobe-Japan1`) | `aj17-kanji.txt` | The notice travels with copies, and a derived work is not presented as a copy or version of the original. |

## How the project applies them

Decided by the project's owner on 2026-11-15.

- **KanjiVG.** A cut made along KanjiVG's stroke groups is a set of contours of the font; KanjiVG
  says which contours go together and none of its data is copied into the cut. Such cuts are
  published. Each names the guide's licence (`licence.guide`), and the file that holds it carries
  KanjiVG's attribution in `terms.notices` and its licence in `terms.guide`, so the attribution
  and the share-alike terms travel with every guided cut.
- **Flat tables.** A table of cuts or skipped attempts holds one description source, as a cut
  file does, and a table of components holds the rows of one source. Rows read from a GPL table
  never sit beside rows read from another.
- **BabelStone Han PUA.** Its glyph is the reference shape of a numbered component. The face is
  in the Song style, and han-compose draws a numbered component with that glyph in its serif and
  kaisho styles. Outlines taken from it stay under the Arphic Public License, in outline files of
  their own, each with a notice of how and when the font's data was changed and with the licence
  text in the release. The pinned font file is mirrored as an asset of this repository's
  releases, unaltered and beside the licence text, because its address upstream is replaced by
  each new version.
- **GlyphWiki.** Free to use. It is cited with its address and stays a check on cuts; its glyphs
  are published only as reference outlines, named with the date they were fetched.

## What is uncertain

- **OFL outlines and GPL labels.** Whether a set of contour indices into an OFL font, labelled
  from a GPL description table, is a derived work of that table is unsettled. Outline files and
  cut files are separate, and cut files and tables are separate per source, so a user can take the
  outlines with the labels of a public-domain or MIT source only.
- **KanjiVG's share-alike and the OFL.** If the contour indices of a guided cut are an adaptation
  of KanjiVG, share-alike asks for CC BY-SA on them, while the OFL allows no other licence on font
  data. The project holds that they are no adaptation and states both terms on the file.
- **BabelStone IDS.** Its header says the data draws on Kawabata Taichi's IDS data, which descends
  from CHISE, and on IRG submissions. The maintainer's statement that the sequences are facts
  covers his file; the terms of what it draws on are not stated there.
- **Reserved Font Name.** Release files are named by font identifier (`noto-sans-cjk-jp@2.004`).
  No file or product name here uses "Source".
- **Adobe-Japan1.** The repository's permission notice is written for its README; `aj17-kanji.txt`
  states no terms of its own. Only CID-to-character relations are taken from it.
- **GlyphWiki.** The licence was read in its English translation, archived on 2025-11-14
  (<https://web.archive.org/web/20251114152951/https://en.glyphwiki.org/wiki/GlyphWiki:License>);
  the page says the Japanese original governs, and that one did not load for an automated client
  on 2026-11-15.
