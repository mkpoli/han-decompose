# Pinned inputs

Every font and table a build reads, with its version, digest and terms. `fonts.json` and
`sources.json` hold the same facts for programs, and a release ships both. This page is written
from them by `han-decompose citations`.

`han-decompose fetch` downloads each file into the cache and refuses one whose SHA-256 differs.

## Fonts

### `noto-sans-cjk-jp@2.004`

- Font: Noto Sans CJK JP 2.004, name-table version `Version 2.004;hotconv 1.0.118;makeotfexe 2.5.65603`, 1000 units per em, read at `wght` 400.
- File: <https://github.com/notofonts/noto-cjk/raw/Sans2.004/Sans/Variable/TTF/NotoSansCJKjp-VF.ttf>
- SHA-256: `240c9b83bf7b386edbae39995ae7e068ed4583f484d92e4a74c34158b5f27b1a`
- Licence: OFL-1.1, stated in the font's name table, record 13 (licence description).
- Copyright: © 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'.
- Reserved Font Names: Source
- Design: `source-han-sans`, grain contour; chain `source-han-sans` (1 of 1).

### `plangothic-p1@2.9.5795`

- Font: Plangothic P1 2.9.5795, name-table version `Version 6.400;July 4, 2026;FontCreator 14.0.0.2901 64-bit`, 1000 units per em.
- File: <https://github.com/Fitzgerald-Porthmouth-Koenigsegg/Plangothic-Project/releases/download/V2.9.5795/PlangothicP1-Regular.ttf>
- SHA-256: `550b5d0775b15405946b18f4843df439a51e69508d7e6778d94c1f7a53dc5ad6`
- Licence: OFL-1.1, stated in the font's name table, record 13 (licence description).
- Copyright: Copyright (c) 2024 by Fitzgerald P. Köeingsegg. All rights reserved.
- Design: `plangothic`, grain piece; chain `plangothic` (1 of 2).

### `plangothic-p2@2.9.5795`

- Font: Plangothic P2 2.9.5795, name-table version `Version 3.179;July 5, 2026;FontCreator 14.0.0.2901 64-bit`, 1000 units per em.
- File: <https://github.com/Fitzgerald-Porthmouth-Koenigsegg/Plangothic-Project/releases/download/V2.9.5795/PlangothicP2-Regular.ttf>
- SHA-256: `681933370adfe0fc7253f77735275a82fea09fe4f8adba907bdeb46c110daf8f`
- Licence: OFL-1.1, stated in the font's name table, record 13 (licence description).
- Copyright: Copyright (c) 2024 by Fitzgerald P. Köeingsegg. All rights reserved.
- Design: `plangothic`, grain piece; chain `plangothic` (2 of 2).

### `noto-serif-cjk-jp@2.003`

- Font: Noto Serif CJK JP 2.003, name-table version `Version 2.003;hotconv 1.1.1;makeotfexe 2.6.0`, 1000 units per em, read at `wght` 400.
- File: <https://github.com/notofonts/noto-cjk/raw/Serif2.003/Serif/Variable/TTF/NotoSerifCJKjp-VF.ttf>
- SHA-256: `c2ff7cffb6ef75193d4406b030eab5aa6503c48004acec6b040327e2fe1e9e51`
- Licence: OFL-1.1, stated in the font's name table, record 13 (licence description).
- Copyright: © 2017-2024 Adobe (http://www.adobe.com/).
- Design: `source-han-serif`, grain contour; chain `source-han-serif` (1 of 1).

### `babelstone-han-pua@1.472`

- Font: BabelStone Han PUA 1.472, name-table version `Version 1.472`, 1024 units per em.
- File: <https://www.babelstone.co.uk/Fonts/Download/BabelStoneHanPUA.ttf>; mirror <https://github.com/mkpoli/han-decompose/releases/download/mirror-babelstone-han-pua-1.472/BabelStoneHanPUA-1.472.ttf>
- SHA-256: `92e7155bd28f5570449f4dc71e9bb6fa919f67ef0120d4f83b58c61bed3ed4dc`
- Licence: Arphic-1999, stated in the font's name table, record 13 (licence description).
- Copyright: (c) Copyright 1994-1999, Arphic Technology Co., Ltd.; (c) Copyright 2009-2025, Andrew West.
- Design: `babelstone-han`, grain piece; chain `babelstone-han` (1 of 1).

## Sources

### `ids-corpus`

- Source: ids-input IDS corpus (data/ids-corpus.json.gz), <https://github.com/mkpoli/ids-input>
- Role: candidates
- Pin: commit ea2691e0c1ac37f27b858b2ee1353bd83536d3ed (2026-11-16); retrieved 2026-11-16.
- Licence: GPL-2.0-or-later. https://github.com/mkpoli/ids-input/blob/ea2691e0c1ac37f27b858b2ee1353bd83536d3ed/docs/ids-corpus.md: the artifact is GPL-2.0-or-later because CHISE's IDS rows are inside it
- Attribution: ids-input data/ids-corpus.json.gz, merging BabelStone IDS by Andrew West (魏安), File Date 2025-06-27, CHISE IDS by the CHISE project, Yi Bai's IDS data (MIT, zi.tools) and ids-input's own rows; read as candidate structures and class rows only, never bundled or redistributed.
- Limits: Merged from several sources, and 4,064 of its 438,656 description rows name a component it gives no identifier. Its class-member rows are candidates a reviewer has not judged.

| File | SHA-256 | Address |
|---|---|---|
| `ids-corpus.json.gz` | `cf089a1c6c0b0785feeaba05a2296dafeb42da05b92881a395c42f4e89a4a305` | <https://raw.githubusercontent.com/mkpoli/ids-input/ea2691e0c1ac37f27b858b2ee1353bd83536d3ed/data/ids-corpus.json.gz> |

### `babelstone`

- Source: BabelStone IDS (Ideographic Description Sequences for CJK Unified Ideographs), <https://www.babelstone.co.uk/CJK/IDS.TXT>
- Role: description
- Pin: File Date 2025-06-27 (Unicode 16.0); retrieved 2026-11-15.
- Licence: LicenseRef-BabelStone-IDS. IDS.TXT header, note 2: under U.S. copyright law data is not eligible for copyright protection, and IDS descriptions are held to be such data; anyone may use the data for personal or commercial purposes without asking permission or providing attribution; the maintainer waives copyright claims to the file's presentation.
- Attribution: BabelStone IDS by Andrew West (魏安), File Date 2025-06-27, https://www.babelstone.co.uk/CJK/IDS.TXT
- Limits: The file has no versioned URL; the pin is its File Date and digest. A sequence describes a character's form in the regions it is tagged with, which need not be the form a given font draws. Its header (note 1) says the data draws on Kawabata Taichi's IDS data and on IRG submissions; note 2 rests on U.S. law.

| File | SHA-256 | Address |
|---|---|---|
| `IDS.TXT` | `cc2a0a97e6a51ed6ebe59870ef2af66e83f3c3c27387d79b4441bb2d791d78b1` | <https://www.babelstone.co.uk/CJK/IDS.TXT><br><https://web.archive.org/web/20250630223601id_/https://babelstone.co.uk/CJK/IDS.TXT> |

### `chise`

- Source: CHISE IDS, <https://gitlab.chise.org/CHISE/ids>
- Role: description
- Pin: commit c3057f890b4d7a990628873f19274ec33b58a7aa (2026-11-01) of the mirror https://github.com/chise/ids; retrieved 2026-11-15.
- Licence: GPL-2.0-or-later. https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/README.md, section License
- Attribution: CHISE IDS, the CHISE project, https://gitlab.chise.org/CHISE/ids
- Limits: CHISE publishes no releases; the pin is a commit. The repository lacks the COPYING file its README points at.

| File | SHA-256 | Address |
|---|---|---|
| `IDS-UCS-Basic.txt` | `497ab2be984a86233848fe3631046351f3bb0334bfaac1d8f836aff2d3f87ba0` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Basic.txt> |
| `IDS-UCS-Compat-Supplement.txt` | `c1d265a791a24a8b4d7d963cb7cf31a6a3b1b234b630477d3f27798c9ccab930` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Compat-Supplement.txt> |
| `IDS-UCS-Compat.txt` | `7683730c8213ecb3a2b3e85daa6b7b913c43b44a81a9af7900671bca4d091391` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Compat.txt> |
| `IDS-UCS-Ext-A.txt` | `d58c5b21054d1ba07fd2621f0892b36c088009d7890b136f42f8c5a5af21f495` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-A.txt> |
| `IDS-UCS-Ext-B-1.txt` | `336be9f156b9c78785a79360978241b1a2973fab5c26662489f69e4d94b13ba0` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-B-1.txt> |
| `IDS-UCS-Ext-B-2.txt` | `551150fa2bd8886c17b5af40ad1d7876026d477349e7d636b0fbfc7306d26b81` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-B-2.txt> |
| `IDS-UCS-Ext-B-3.txt` | `33a51a09a18d06fb666e72f13d3854c41a1d06207f0f0c4ac43f3687a0bea6fb` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-B-3.txt> |
| `IDS-UCS-Ext-B-4.txt` | `f6c926482a3600e93b17be958de8cce701c0d91c644316a87e3a821374ad4360` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-B-4.txt> |
| `IDS-UCS-Ext-B-5.txt` | `21cf28e9e4aeb3d98e8c7739899270b13a6d080a2f65f0d4287710d71e72901a` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-B-5.txt> |
| `IDS-UCS-Ext-B-6.txt` | `a732d18a27f418cb4610b7a1e1674487485111734cbd131220caa1baf23b630a` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-B-6.txt> |
| `IDS-UCS-Ext-C.txt` | `74dcff528d54508225e587384f132cac508b97a866969ebbeea848a030910225` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-C.txt> |
| `IDS-UCS-Ext-D.txt` | `c300f9ace1ffd9526fe3c17a12c94b3823e1a97cd507bd4b85b784bf269a3234` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-D.txt> |
| `IDS-UCS-Ext-E.txt` | `aab22be5a0ba07d3830f37f344b08950c566286171539c08ce6d0d0a5f3a635b` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-E.txt> |
| `IDS-UCS-Ext-F.txt` | `dfede4731416ad43a084d0ecdc86562607e9057735e9ac43114870fa5dbf9f5e` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-F.txt> |
| `IDS-UCS-Ext-G.txt` | `1f8f8cc7d911ccf86c196ce4de43d7e4ca03689ee83d4e3e380120eac336c64d` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-G.txt> |
| `IDS-UCS-Ext-H.txt` | `e239d31373777a953c755ba99ae7a502a33823bddd0fc9af4e61e3cd8f209e0c` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-H.txt> |
| `IDS-UCS-Ext-I.txt` | `a84694c801290033b7e3f79303c71fcdcae595afc3a47481496dc051832369d0` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-I.txt> |
| `IDS-UCS-Ext-J.txt` | `0910def2870d1e4cb38c4064f060de5efc48bb73fee6d5f7447657fa121fa260` | <https://raw.githubusercontent.com/chise/ids/c3057f890b4d7a990628873f19274ec33b58a7aa/IDS-UCS-Ext-J.txt> |

### `zi-tools`

- Source: Yi Bai's IDS data, level 1 (zi.tools notation), <https://github.com/yi-bai/ids>
- Role: description
- Pin: commit da1e9f8a09e2ec8faaf176bac99203f978282041 (2026-10-20); retrieved 2026-11-15.
- Licence: MIT. https://raw.githubusercontent.com/yi-bai/ids/da1e9f8a09e2ec8faaf176bac99203f978282041/LICENSE
- Attribution: Copyright (c) 2021 Yi Bai, https://github.com/yi-bai/ids

| File | SHA-256 | Address |
|---|---|---|
| `ids_lv1.txt` | `51f78d7d84f52fd73e5bc155c2239b737c58ce627d446894a809f1a36547ae18` | <https://raw.githubusercontent.com/yi-bai/ids/da1e9f8a09e2ec8faaf176bac99203f978282041/ids_lv1.txt> |

### `kanjivg`

- Source: KanjiVG, <https://kanjivg.tagaini.net/>
- Role: guide
- Pin: release r20260714; retrieved 2026-11-15.
- Licence: CC-BY-SA-3.0. https://github.com/KanjiVG/kanjivg/blob/r20260714/COPYING
- Attribution: KanjiVG, Copyright (C) 2009-2013 Ulrich Apel, CC BY-SA 3.0, https://kanjivg.tagaini.net/
- Limits: Its groups follow Japanese stroke order and component analysis, which can differ from the description a cut is labelled with.

| File | SHA-256 | Address |
|---|---|---|
| `kanjivg-20260714.xml.gz` | `d4a8e5e11533fe6a5d81a158b2c153964322641d2982c90a919461f3c06dca6b` | <https://github.com/KanjiVG/kanjivg/releases/download/r20260714/kanjivg-20260714.xml.gz> |

### `glyphwiki`

- Source: GlyphWiki, <https://glyphwiki.org/>
- Role: reference
- Pin: glyphs fetched 2026-11-13 by ids-input, as its data/custom-outlines.json.gz at commit be70733a179085a16e48f7049b6cfec5e07f4496; retrieved 2026-11-15.
- Licence: LicenseRef-GlyphWiki. https://glyphwiki.org/wiki/GlyphWiki:データ・記事のライセンス; English translation of its revision 15, archived 2025-11-14: https://web.archive.org/web/20251114152951/https://en.glyphwiki.org/wiki/GlyphWiki:License
- Attribution: GlyphWiki, https://glyphwiki.org/
- Limits: Glyphs are edited by GlyphWiki's users and may differ from the form a description source means. A glyph is used only to check a cut. The Japanese licence page, which governs, did not load for an automated client on 2026-11-15; the English translation was read from an archive.

| File | SHA-256 | Address |
|---|---|---|
| `custom-outlines.json.gz` | `9750f7beacbaef4458e1ff5e8542793007e8d134e8c7c0eaf638c86ce8921ee3` | <https://raw.githubusercontent.com/mkpoli/ids-input/be70733a179085a16e48f7049b6cfec5e07f4496/data/custom-outlines.json.gz> |

### `adobe-japan1`

- Source: Adobe-Japan1-7 Kanji Datafile (aj17-kanji.txt), <https://github.com/adobe-type-tools/Adobe-Japan1>
- Role: identity
- Pin: Version 2023-01-24, commit b42b377d7efbc233ae2a4c1833947e04760e68d1; retrieved 2026-11-15.
- Licence: LicenseRef-Adobe-Japan1. https://raw.githubusercontent.com/adobe-type-tools/Adobe-Japan1/b42b377d7efbc233ae2a4c1833947e04760e68d1/README.md
- Attribution: Adobe-Japan1-7 Kanji Datafile, Version 2023-01-24, prepared by Ken Lunde and Masataka Hattori; © 1992–2019 Adobe Inc.
- Limits: The repository's permission notice is written for its README; the data file states no terms of its own. None of the pinned fonts is keyed to Adobe-Japan1, so no outline here shows a CID's glyph.

| File | SHA-256 | Address |
|---|---|---|
| `aj17-kanji.txt` | `b277fbe06a6b7566c9dda81ba920d0750bf2d620d6066e57153d36ed0924d77d` | <https://raw.githubusercontent.com/adobe-type-tools/Adobe-Japan1/b42b377d7efbc233ae2a4c1833947e04760e68d1/aj17-kanji.txt> |

### `ids-input-components`

- Source: ids-input custom component registry, <https://github.com/mkpoli/ids-input>
- Role: identity
- Pin: commit be70733a179085a16e48f7049b6cfec5e07f4496; retrieved 2026-11-15.
- Licence: GPL-2.0-or-later. https://raw.githubusercontent.com/mkpoli/ids-input/be70733a179085a16e48f7049b6cfec5e07f4496/data/README.md
- Attribution: ids-input custom component registry, https://github.com/mkpoli/ids-input; derived from BabelStone IDS, CHISE IDS and Yi Bai's IDS data
- Limits: Every equivalence in it is derived by comparing the three tables' descriptions of shared characters; no source states one.

| File | SHA-256 | Address |
|---|---|---|
| `custom-components.json.gz` | `3e88359acb1a5fa7d9202a004f0ce65266adf1fad03140d55ead835e57379261` | <https://raw.githubusercontent.com/mkpoli/ids-input/be70733a179085a16e48f7049b6cfec5e07f4496/data/custom-components.json.gz> |
| `custom-ids.tsv` | `b1c394894f726e240a1e574a2226a42dfb1759e06387f64db59d45eb9e577d92` | <https://raw.githubusercontent.com/mkpoli/ids-input/be70733a179085a16e48f7049b6cfec5e07f4496/data/custom-ids.tsv> |

### `han-compose-numbered-forms`

- Source: han-compose numbered component forms (data/numbered-forms.json), <https://github.com/mkpoli/han-compose>
- Role: cuts
- Pin: commit 3587faa97f4e7672479133609b3b2d7c0aa3d4d2; retrieved 2026-11-15.
- Licence: OFL-1.1. The file's own `sources` block names the fonts of the Sans forms (Noto Sans CJK JP 2.004, Plangothic P1 and P2 V2.9.5795) with SIL OFL 1.1, and BabelStone Han PUA 1.472 with the Arphic Public License; https://raw.githubusercontent.com/mkpoli/han-compose/3587faa97f4e7672479133609b3b2d7c0aa3d4d2/data/README.md says the Sans forms are cut from those Noto and Plangothic glyphs and the Serif and Kaisho forms are the PUA glyph itself.
- Attribution: han-compose, data/numbered-forms.json, https://github.com/mkpoli/han-compose; Sans forms cut with han-compose bf13d98 from Noto Sans CJK JP 2.004 and Plangothic 2.9.5795
- Limits: The file holds outlines without the host or the contours they were cut from, and does not say how each was cut. A form is imported only where its outline is whole contours of a host glyph at the same position; the Serif and Kaisho forms, which are PUA glyphs under the Arphic Public License, are not taken from it.

| File | SHA-256 | Address |
|---|---|---|
| `numbered-forms.json` | `af63ab13f110ade1696c0353b148f18a2683232660609ddba3af0cc619c9ad2b` | <https://raw.githubusercontent.com/mkpoli/han-compose/3587faa97f4e7672479133609b3b2d7c0aa3d4d2/data/numbered-forms.json> |

### `unihan`

- Source: Unihan database, <https://www.unicode.org/Public/18.0.0/ucd/Unihan.zip>
- Role: classes
- Pin: Unicode 18.0.0, file date 2026-07-31; retrieved 2026-11-16.
- Licence: Unicode-3.0. https://www.unicode.org/license.txt (Unicode License V3, copyright 1991-2026 Unicode, Inc.), which the header of Unihan_RadicalStrokeCounts.txt in the archive points to as the terms of use
- Attribution: Unihan database, Unicode 18.0.0, © 2026 Unicode, Inc.
- Limits: Only `kRSUnicode` is read, for the class rows whose basis is `radical-index`; a radical index says which radical a character is indexed under and not that two shapes are one component.

| File | SHA-256 | Address |
|---|---|---|
| `Unihan.zip` | `4c93ea9c1f636451729a840978f1667a53886af37ba854fdcce109721c63d43e` | <https://www.unicode.org/Public/18.0.0/ucd/Unihan.zip> |
