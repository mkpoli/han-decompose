# Data format 1

This document defines the files of a han-decompose release. `schema/1/han-decompose.schema.json`
states the same structure for machines; where the two differ, this text governs.

The schema describes a file of version 1.0 exactly and refuses any other property. A reader
ignores properties it does not know, so that a file of a later minor version still reads.

No string in any file holds a control character (U+0000–U+001F, U+007F). Text is kept as its
source writes it, without Unicode normalisation.

## 1. Terms

| Term | Meaning |
|---|---|
| font | One pinned font file at one named instance (`wght` 400 for a variable font). |
| glyph | One glyph of a font, selected by code point, variation sequence or glyph index. |
| contour | One closed contour of a glyph, in the font's own order. Contours may overlap. |
| piece | A maximal set of contours whose ink overlaps or runs along a shared edge, with the counters inside it. Contours that only meet at a point are apart, unless one contour runs through both. |
| description | One IDS a source gives for a subject. |
| component | What a node of a description names. |
| reading | One labelling of one glyph by one description: which contours go to which nodes. |
| cut | One node of a reading: a component, its path in the tree and its contour set. |
| verdict | A reviewer's right or wrong on one cut with one exact contour set. |

## 2. Identifiers

Identifiers are strings. An identifier stays the same across rebuilds while the inputs it names
are unchanged.

### 2.1 Font

`<family-slug>@<version>`, as `noto-sans-cjk-jp@2.004`. The slug is lower-case ASCII letters and
digits joined by hyphens; the version is ASCII letters and digits joined by dots. A new version of
a font is a new font. Each face of a collection is a font with a slug of its own.

### 2.2 Glyph

`<font>/<selector>`. A selector is one of:

| Selector | Selects |
|---|---|
| `U+50AC` | The glyph the font maps the code point to. |
| `U+845B.E0100` | The glyph the font maps the variation sequence to. |
| `gid.1234` | The glyph at that index, for a glyph no code point reaches. |

A code point has one spelling: upper-case hex of at least four digits with no further leading zero
(`U+50AC`, `U+20B36`), surrogates excluded. The second code point of a sequence is a variation
selector, U+FE00–U+FE0F or U+E0100–U+E01EF. Decimal numbers, here and in every other identifier,
have no leading zero.

### 2.3 Description

`<source>.<h8>`. `<source>` is a source identifier (`babelstone`, `chise`, `zi-tools`). `<h8>` is
the first eight hex digits of the SHA-256 of the description's text in UTF-8.

The text is the IDS as the source writes it, without what the source attaches to it:

| Source | Text | Attached, kept as `tags` |
|---|---|---|
| `babelstone` | What stands between `^` and `$`. | The region letters in the parentheses that follow. |
| `chise` | The third field of a line. The value of an `@apparent=` field is a description of its own. | `apparent` for an `@apparent=` description. |
| `zi-tools` | One alternative of a field, fields being split at `;`. | — |

`⿰亻崔` gives `9d9dea39`, so BabelStone's description of 催 is `babelstone.9d9dea39`.

A text a source gives twice for one subject is one description; the tags of each occurrence are
joined by a space.

Eight hex digits do not keep every text of a source apart. A description identifier is used
together with its subject or its glyph, and the text itself (`ids`) stands beside it wherever it
appears.

### 2.4 Component

`<kind>:<value>`.

| Kind | Reference | Written in a description as | Value |
|---|---|---|---|
| character | `u:5C71`, `u:845B.E0100` | 山 | Code point in hex, with a variation selector after a dot. |
| BabelStone numbered component | `bs:42` | `{42}` | The number. |
| CHISE entity | `chise:CDP-8958` | `&CDP-8958;` | The entity's name. |
| Adobe-Japan1 glyph | `aj1:1815` | — | The CID. |
| zi.tools stroke chain | `zi:#(丿𠃊)` | `#(丿𠃊)` | The chain as written. |
| subtree | `ids:⿱𰀪亻` | `⿱𰀪亻` | The node's own IDS, starting with its operator, for a node no source names. |

An operator is an ideographic description character (U+2FF0–U+2FFF, U+31EF) or the variation
indicator `〾` (U+303E), which BabelStone writes before a variant form of its one operand.

### 2.5 Path

A node's place in the tree of a reading: the operand indices from the root, counted from 0. As
text the indices are joined by dots (`1.0`) and the root is `-`.

### 2.6 Cut and signature

A cut is `<glyph>~<description>~<path>`:
`noto-sans-cjk-jp@2.004/U+50AC~babelstone.9d9dea39~1.0`.

A release holds at most one reading of a glyph under a description, so the identifier names one
cut.

Its signature `sig` is the first eight hex digits of the SHA-256 of its component reference and
its contour indices, ascending, in decimal, all joined by single spaces. 山 at contours `[0, 2]`
hashes the text `u:5C71 0 2` and gives `785ad39d`. A verdict binds to the identifier and the
signature together, so it stops applying when the component or the contour set changes.

## 3. Coordinates and numbers

- The em is 1000 units, y up, whatever the font's own em; the font's `upem` is in the registry.
- Contour points are integers in hundredths of a unit (`q` is 100): the font's coordinate times
  100000 / `upem`, rounded to the nearest integer, a tie going to the even one.
- Boxes are `[x0, y0, x1, y1]` in units and span every point of the contours they cover, control
  points included.
- Lengths and areas carry at most two decimals, scores at most four, rounded the same way.

## 4. Files

A release is laid out as:

```
manifest.json
fonts.json  sources.json
components.tsv
outlines/<font>/<block>.json.gz
cuts/<font>/<source>/<block>.json.gz
library/<chain>.json.gz  forms/<chain>.json.gz
references/<source>.json.gz
cuts.tsv.gz  skipped.tsv.gz  verdicts.tsv
LICENSES/  NOTICE.md  SHA256SUMS
```

`<block>` is the glyph's code point divided by 256, in lower-case hex of at least three digits:
`050` holds U+5000–U+50FF and `20b` holds U+20B00–U+20BFF. A variation sequence goes by its base.
Glyphs selected by index are in `gid`. A skipped attempt whose subject no font draws is filed by
the subject's code point, in the files of the chain's first font; a subject that is no character,
in `gid`.

Every JSON file is UTF-8 on one line, with sorted keys, the separators `,` and `:`, and characters
outside ASCII written as themselves. A number without a fractional part is written without one
(`366`); any other is written in positional decimal with the fewest digits that read back to the
same value. A `.gz` file is gzip with its modification time set to 0. No file holds a build date.

Every JSON file names its format: `han-decompose/<kind>@<major>.<minor>`. A minor version adds
properties; a major version changes or removes them.

`manifest.json`, the `library`, `forms` and `references` files are reserved in this version.

### 4.1 `fonts.json`

`format` is `han-decompose/fonts@1.0`.

`fonts` lists one object per font:

| Property | Required | Value |
|---|---|---|
| `id` | yes | Font identifier. |
| `name`, `version` | yes | Family name and the version in the identifier. |
| `nameVersion` | | The font's name-table version string. |
| `file` | yes | File name in the cache: ASCII letters, digits, `.`, `_` and `-`, starting with a letter or digit. |
| `url` | yes | Where the file is fetched from, or the archive that holds it. |
| `sha256` | yes | Digest of the font file. |
| `archive` | | `{sha256, member}`: digest of the archive at `url` and the member that is the font. |
| `index` | | The face's index when the file is a collection. |
| `instance` | | Axis values the outlines are read at: `{"wght": 400}`. |
| `upem` | yes | The font's units per em. |
| `licence` | yes | SPDX expression. |
| `licenceEvidence` | | Where the font states its terms. |
| `licenceFile` | | The licence text under `LICENSES/`. |
| `copyright` | yes | The font's copyright line. |
| `reservedNames` | | Reserved Font Names. |
| `style` | yes | `sans`, `serif`, `kaisho`, `fangsong` or `other`. |

`chains` maps a chain name to font identifiers in order. A chain is one design spread over
several fonts; a glyph is taken from the first font of the chain that draws it.

### 4.2 `sources.json`

`format` is `han-decompose/sources@1.0`. `sources` lists one object per source:

| Property | Required | Value |
|---|---|---|
| `id`, `name` | yes | Source identifier and title. |
| `role` | yes | `description` (its IDS label the cuts), `guide` (cuts follow its groups), `reference` (cuts are compared with its glyphs) or `identity` (it relates components). |
| `url` | yes | The source's home. |
| `pin` | yes | A release, a commit or a file date. |
| `retrieved` | yes | `YYYY-MM-DD`. |
| `files` | | Per file: `file` (a name as for a font), `url`, `sha256`, and `mirrors` serving the same bytes. |
| `licence` | yes | SPDX expression. Terms SPDX does not list are `LicenseRef-<name>`. |
| `licenceEvidence` | | Where the source states its terms. |
| `licenceFile` | | The licence text under `LICENSES/`. |
| `attribution` | yes | The line to credit the source with. |
| `weakness` | | What limits the source's authority. |

### 4.3 Outline files

One file holds glyphs of one font and of one block. `format` is `han-decompose/outlines@1.0`.

| Property | Value |
|---|---|
| `font` | Font identifier. |
| `licence`, `copyright` | The font's, repeated from the registry. |
| `em`, `q` | 1000 and 100. |
| `glyphs` | Selector → glyph. |

A glyph:

| Property | Value |
|---|---|
| `contours` | The glyph's contours in the font's order, composites decomposed. Each is `[commands, points]`. |
| `pieces` | The contour indices of each piece, ascending; pieces ordered by their first index. Every contour is in exactly one piece. |
| `box` | The box of all contours. |
| `advance` | The advance width in units. |

`commands` is a string of pen commands. `points` holds x and y interleaved, in command order.

| Command | Points | Meaning |
|---|---|---|
| `M` | 1 | Start of the contour. Always first, and only there. |
| `L` | 1 | Line to the point. |
| `Q<n>` | n | A TrueType quadratic run: n − 1 off-curve points and the on-curve point that ends it. |
| `C` | 3 | Cubic curve: two control points and the end point. |
| `Q<n>*` | n | The whole of a contour that has no on-curve point: n off-curve points of a closed quadratic run. It stands alone, without `M`. |

A contour closes with a straight line from its last point to its first. Where the font closes it
with a curve, that curve's end point repeats the first point. Curves are kept as the font has them.

Only glyphs that a reading, a skipped attempt or a reference names are written.

### 4.4 Cut files

One file holds the readings of one font's glyphs under one description source, by the block of
the glyph. It holds indices and labels and no outline. `format` is `han-decompose/cuts@1.0`.

| Property | Value |
|---|---|
| `font`, `source` | Font and source identifiers. |
| `terms` | `outline`: the font's licence. `description`: the source's. `guide`: the guide's, when cuts follow one. `notices`: the copyright and attribution lines of the font and the sources. |
| `readings` | Readings. |
| `skipped` | Attempts that closed no reading. |

A reading:

| Property | Required | Value |
|---|---|---|
| `glyph` | yes | Glyph identifier. |
| `subject` | yes | The component the description is of. |
| `description` | yes | Description identifier. |
| `ids` | yes | The description's text (2.3). |
| `tags` | | What the source attaches to the description, as written. |
| `tree` | yes | The description spelled out as far as the cut went: 催 `⿰亻崔` becomes `⿰亻⿱山隹`. |
| `opened` | | The nodes of `tree` that came from a component's own description: `path`, `component`, `description` and its text `ids`. The root is never one. |
| `method` | yes | `name`: `deal`, `lift`, `axis`, `kanjivg` or `hand`. `tool`, with `version` and `commit`. `grain`: `piece` when whole pieces were assigned, `contour` when single contours were. `guide`: a source identifier. |
| `complete` | yes | Whether every contour of the glyph is in a cut and every leaf of `tree` has one. |
| `evidence` | | Scores of the reading as a whole. |
| `cuts` | yes | One cut per labelled node. |

An inner node is stored only where its contour set differs from the union of its children's.

A cut:

| Property | Required | Value |
|---|---|---|
| `id`, `sig` | yes | 2.6. |
| `path` | yes | Operand indices into `tree`. |
| `place` | yes | Where the node stands in its parent: `L`, `C`, `R` under `⿰` and `⿲`; `T`, `M`, `B` under `⿱` and `⿳`; otherwise the operator and the operand index, as `⿸0`. Empty for the root. |
| `component` | yes | Component reference. |
| `text` | yes | The node as the description writes it. |
| `contours` | yes | Contour indices, ascending. |
| `box` | yes | Box of the cut's contours. |
| `frame` | | Box of the parent node's ink. |
| `gap`, `area`, `ink` | | Distance to the nearest sibling ink, filled area, and summed length of the contours' polygons. |
| `evidence` | | Scores of the cut: `fit` or `match`, `margin`, `agree`, `reference`. |
| `checks` | | Per check (`filled`, `skeleton`, `windows`): `value`, `limit`, `pass`, and `against`, the glyph compared with. |
| `calibrated` | | The component whose reviewed labels set the checks' limits, or `false`. |
| `status` | yes | `accepted`, `refused` (a check failed), `reviewed-right` or `reviewed-wrong`. |
| `licence` | yes | `outline` and `description` as in the file's `terms`; `guide`, as in the terms, exactly when the reading's method names a guide. |

Within a file, a glyph has at most one reading under a description. A subject that is a character
is read on the glyph of its own code point.

Within a reading:

- no path is labelled twice;
- a cut's contours are a subset of the contours of every cut above it on its path;
- cuts on different branches share no contour;
- a cut's `component` is the reference of its `text` (2.4).

A skipped attempt holds `subject`, `glyph` when a font draws the subject, `description`, `ids`,
`tags`, and `reason`: a `code` and a sentence `text`.

| Code | Meaning |
|---|---|
| `too-few-pieces` | Fewer pieces than operands. |
| `too-many-pieces` | More pieces than the cutter divides. |
| `unlike-element` | No division resembles the operands. |
| `layout-mismatch` | The pieces do not lie as the operator says. |
| `ambiguous` | Two divisions score alike. |
| `does-not-tile` | The pieces do not add up to the glyph. |
| `no-reference-glyph` | No font draws an operand to compare with. |
| `no-enclosure` | No enclosing part was found. |
| `no-face` | No font of the chain draws the subject. |
| `no-ink` | The glyph draws nothing. |
| `unlike-whole` | The operands, each drawn where its pieces sit, do not come out as the glyph. |
| `unreadable-description` | The description does not read as a tree. |

## 5. Tables

A table is UTF-8 text with tab-separated fields and lines ending in a line feed. Its first line
is `# format=han-decompose/<name>-tsv@1.0`, followed by ` release=<version>` in a release; a
release name holds ASCII letters, digits, `.`, `_`, `+` and `-`. The second line names the columns,
in the order given below. An absent value is empty.

Numbers are written as in the JSON files (section 4).

### 5.1 `cuts`

One row per cut. Each row stands alone.

| Column | Value |
|---|---|
| `cut_id`, `sig` | 2.6. |
| `font`, `glyph` | Font identifier and glyph selector. |
| `char` | The subject, when it is a character. |
| `source`, `description`, `ids`, `tree` | As in the reading. |
| `path` | Path as text (2.5). |
| `place` | As in the cut. |
| `level` | 1 for a node of the subject's own description, one more for each opened node above it. |
| `whole` | `1` when the node's parent is the root, else `0`. |
| `component`, `text` | As in the cut. |
| `contours` | Indices separated by spaces. |
| `grain` | From the reading's method. |
| `box`, `frame` | Four numbers separated by spaces. |
| `method`, `tool` | The method's `name` and `tool`. |
| `fit`, `margin`, `agree`, `reference` | From the cut's evidence; `fit` takes `match` where the cut has no `fit`. |
| `filled`, `skeleton` | The checks' values. |
| `calibrated` | A component reference, or `0` for `false`. |
| `status` | As in the cut. |
| `licence_outline`, `licence_description`, `licence_guide` | From the cut's `licence`. |

The table holds no outline. A reader joins `font`, `glyph` and `contours` to the outline files.

### 5.2 `skipped`

`font`, `glyph`, `char`, `source`, `description`, `ids`, `reason_code`, `reason`.

### 5.3 `components`

One row per component, or per relation between two.

| Column | Value |
|---|---|
| `component` | Component reference. |
| `kind` | By the reference's kind: `character` (`u`), `babelstone` (`bs`), `chise`, `adobe-japan1` (`aj1`), `zi-tools` (`zi`) or `subtree` (`ids`). |
| `text` | The component as written (2.4); empty for an Adobe-Japan1 glyph. |
| `relation` | `same` (two names of one thing), `glyph-of` (a glyph of a character) or `equivalent` (the same shape in another notation). |
| `target` | The other component. |
| `basis` | What the relation rests on. |
| `tier` | `source` when a source states the relation, `derived` when it is inferred. |
| `source` | The source identifier. |

`relation`, `target` and `tier` are filled together or all empty.

### 5.4 `verdicts`

| Column | Value |
|---|---|
| `cut_id`, `sig` | The cut and the contour set judged. |
| `verdict` | `right` or `wrong`. |
| `note`, `reviewer` | Free text. |
| `at` | `YYYY-MM-DDThh:mm:ssZ`. |
| `release` | The release the cut was seen in. |

A verdict whose `sig` differs from the built cut's applies to nothing.

## 6. Tiers

The outline is the font's. A cut's label is the builder's unless its status says a reviewer judged
it. A relation between components is `source` or `derived`. Nothing derived is presented as
attested.
