# Data format 2

This document defines the files of a han-decompose release. `schema/2/han-decompose.schema.json`
states the same structure for machines; where the two differ, this text governs.

The schema describes a file of version 2.0 exactly and refuses any other property. A reader
ignores properties it does not know, so that a file of a later minor version still reads.

No string in any file holds a control character (U+0000–U+001F, U+007F). Text is not Unicode
normalised.

## 1. Terms

| Term | Meaning |
|---|---|
| font | One pinned font file at one named instance (`wght` 400 for a variable font). |
| design | Fonts that draw with the same outlines, original or rebuilt from them. |
| chain | A design's fonts in coverage order. |
| glyph | One glyph of a font, selected by code point, variation sequence or glyph index. |
| contour | One closed contour of a glyph, in the font's own order. Contours may overlap. |
| piece | A maximal set of contours whose ink overlaps or runs along a shared edge, with the counters inside it. Contours that only meet at a point are apart, unless one contour runs through both. |
| class | Components that are one thing in different shapes, under a canonical member. |
| structure | An operator tree whose components are written as their classes' canonical members. |
| style | The class member a cut is drawn as. |
| layer | A contour set with its component: a glyph, or a cut opened into its parts. |
| reading | One structure applied to one layer: which contours go to which nodes. |
| cut | One node of a reading: a component, its path and its contour set. |
| drawn IDS | A glyph's accepted structure written with each node's style. |
| verdict | A reviewer's right or wrong on one cut with one exact contour set, or a style named for it. |

## 2. Identifiers and notation

Identifiers are strings. An identifier stays the same across rebuilds while the inputs it names
are unchanged.

### 2.1 Font

`<family-slug>@<version>`, as `noto-sans-cjk-jp@2.004`. The slug is lower-case ASCII letters and
digits joined by hyphens; the version is ASCII letters and digits joined by dots. A new version of
a font is a new font. Each face of a collection is a font with a slug of its own.

### 2.2 Design

A slug as for a font, without a version: `source-han-sans`.

### 2.3 Glyph

`<font>/<selector>`. A selector is one of:

| Selector | Selects |
|---|---|
| `U+50AC` | The glyph the font maps the code point to. |
| `U+845B.E0100` | The glyph the font maps the variation sequence to. |
| `gid.1234` | The glyph at that index, for a glyph no code point reaches. |
| `name.u793e-j` | The GlyphWiki glyph of that name. |

A code point has one spelling: upper-case hex of at least four digits with no further leading zero
(`U+50AC`, `U+20B36`), surrogates excluded. A code point selects GlyphWiki's glyph `u` plus the
code point in lower-case hex (`u793e`), its aliases followed. The second code point of a sequence is a variation
selector, U+FE00–U+FE0F or U+E0100–U+E01EF. Decimal numbers, here and in every other identifier,
have no leading zero.

### 2.4 Notation

Structures and drawn IDS are written in one notation: ideographic description characters
(U+2FF0–U+2FFF, U+31EF), the variation indicator `〾` (U+303E) before a variant form of its one
operand, and components. A component is written as its character; a component no code point names
is written as its own IDS where one is known, else as `&X-NNNNN;`, its identifier in ids-input's
component ledger.

### 2.5 Component

`<kind>:<value>`.

| Kind | Reference | Written as | Value |
|---|---|---|---|
| character | `u:5C71`, `u:845B.E0100` | 山 | Code point in hex, with a variation selector after a dot. |
| subtree | `ids:⿸⿹丅丿丨` | `⿸⿹丅丿丨` | The node's IDS, starting with its operator. |
| ledger | `x:X-00777` | `&X-00777;` | The ledger identifier. |
| Adobe-Japan1 glyph | `aj1:1815` | — | The CID. |

### 2.6 Structure

`s.<h8>`, `<h8>` being the first eight hex digits of the SHA-256 of the structure's text in
UTF-8. The text writes every component as its class's canonical member (section 5.3):
`⿰礻土` and `⿰示土` are both the structure `⿰示土`, `s.0a1c0fdb`.

Eight hex digits do not keep every structure apart. A structure identifier is used together with
its glyph or character, and the text stands beside it wherever it appears.

### 2.7 Path and cut

A path is a node's place in one reading's tree: the operand indices from the root, counted from 0,
joined by dots (`1.0`). The root is `-`.

A cut is `<glyph>~<step>…`, one step per layer from the glyph down, each `<h8>:<path>` with the
`h8` of the structure that layer was read as: `noto-sans-cjk-jp@2.004/U+793E~0a1c0fdb:0` is the
left part of 社 read as `⿰示土`.

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
manifest.json  fonts.json
components.tsv  classes.tsv
outlines/<font>/<block>.json.gz
cuts/<font>/<block>.json.gz
library/<design>.json.gz  forms/<design>.json.gz
cuts.tsv.gz  drawn.tsv.gz  structures.tsv.gz  skipped.tsv.gz  verdicts.tsv
LICENSES/  README.md  SHA256SUMS
```

`<block>` is the glyph's code point divided by 256, in lower-case hex of at least three digits:
`050` holds U+5000–U+50FF and `20b` holds U+20B00–U+20BFF. A variation sequence goes by its base.
Glyphs selected by index are in `gid`, glyphs selected by name in `name`. A skipped attempt without a glyph (no font draws
the subject, or the glyph has no ink) is filed by the subject's code point, in the files of the
design's first font; a subject that is no character, in `gid`.

Every JSON file is UTF-8 on one line, with sorted keys, the separators `,` and `:`, and characters
outside ASCII written as themselves. A number without a fractional part is written without one
(`366`); any other is written in positional decimal with the fewest digits that read back to the
same value. A `.gz` file is gzip with its modification time set to 0. No file holds a build date.

Every JSON file names its format: `han-decompose/<kind>@<major>.<minor>`. A minor version adds
properties; a major version changes or removes them.

`manifest.json`, `format` `han-decompose/manifest@2.0`, holds the `release` name; the `tool` that
built it (`name`, `version`, `commit`); the pinned `fonts` with their digests; `counts` per font
(`readings`, `skipped`, `cuts` by status, `structures`, `classes` with an accepted cut); and
`files`, every file but itself and `SHA256SUMS` with its `path`, `bytes` and `sha256`.
`SHA256SUMS` lists the same digests and the manifest's.

`README.md` names every font of the release with its licence and copyright line, states that every
other file is under CC0-1.0, and `LICENSES/` holds the licence texts.

### 4.1 `fonts.json`

`format` is `han-decompose/fonts@2.0`.

`fonts` lists one object per font:

| Property | Required | Value |
|---|---|---|
| `id` | yes | Font identifier. |
| `name`, `version` | yes | Family name and the version in the identifier. |
| `nameVersion` | | The font's name-table version string. |
| `file` | yes | File name in the cache: ASCII letters, digits, `.`, `_` and `-`, starting with a letter or digit. |
| `url` | yes | Where the file is fetched from, or the archive that holds it. |
| `mirrors` | | Other addresses that serve the same bytes, tried in order after `url`. |
| `sha256` | yes | Digest of the font file. |
| `archive` | | `{sha256, member}`: digest of the archive that `url` and the mirrors serve, and the member that is the font. |
| `index` | | The face's index when the file is a collection. |
| `instance` | | Axis values the outlines are read at: `{"wght": 400}`. |
| `upem` | yes | The font's units per em. |
| `licence` | yes | SPDX expression. |
| `licenceEvidence` | | Where the font states its terms. |
| `licenceFile` | | The licence text under `LICENSES/`. |
| `copyright` | yes | The font's copyright line. |
| `reservedNames` | | Reserved Font Names. |
| `style` | yes | `sans`, `serif`, `kaisho`, `fangsong` or `other`. |
| `design` | yes | Design identifier. |

GlyphWiki is one font, `glyphwiki@<YYYYMMDD>` after the date of the dump read: its `url` and
`sha256` are the dump's, `file` its cache name, `upem` 200, `licence` `LicenseRef-GlyphWiki`, and
`renderer` names the KAGE engine's commit and style (`mincho`). Its contours are the polygons the
engine draws per stroke, not joined.

`designs` lists one object per design: `id`, `name`, `style`, `chain` (font identifiers in
coverage order; a glyph is taken from the first that draws it), and `members`, per font of the
design that is or was considered for it, `font` (an identifier, or a name for a font not pinned)
and `evidence`, the sentences and measurements that place it.

### 4.2 Outline files

One file holds glyphs of one font and of one block. `format` is `han-decompose/outlines@2.0`.

| Property | Value |
|---|---|
| `font` | Font identifier. |
| `licence`, `copyright` | The font's, repeated from the registry. |
| `notice` | How the font's data was changed, in the files of a font whose licence asks a changed copy to say so (the Arphic Public License). |
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

### 4.3 Cut files

One file holds the readings and drawn IDS of one font's glyphs, by the block of the glyph. It
holds indices and labels and no outline. `format` is `han-decompose/cuts@2.0`.

| Property | Value |
|---|---|
| `font` | Font identifier. |
| `design` | Its design. |
| `drawn` | Glyph selector → drawn IDS. |
| `readings` | Readings. |
| `skipped` | Attempts that closed no reading. |

A drawn IDS:

| Property | Required | Value |
|---|---|---|
| `ids` | yes | The structure written with each cut's style, opened layers written in place: `⿰礻土`. |
| `structure` | yes | Structure identifier and `text`. |
| `readings` | yes | The readings it is written from, as their layer steps. |
| `tier` | yes | `machine`, or `reviewed` when every style in it is. |

A reading:

| Property | Required | Value |
|---|---|---|
| `glyph` | yes | Glyph identifier. |
| `subject` | yes | The component the layer stands for. |
| `layer` | yes | The steps (2.7) from the glyph to the cut this reading divides; empty for the glyph. |
| `structure` | yes | Structure identifier. |
| `text` | yes | The structure's text. |
| `tree` | yes | The structure spelled out as far as the cut went: 催 `⿰亻崔` becomes `⿰亻⿱山隹`. |
| `opened` | | The nodes of `tree` read as layers below: `path`, `component`, `structure` and its `text`. |
| `method` | yes | `name`: `deal`, `lift`, `kage`, `axis`, `kanjivg` or `hand`. `tool`, with `version` and `commit`. `grain`: `piece` when whole pieces were assigned, `contour` when single contours were. |
| `complete` | yes | Whether every contour of the layer is in a cut and every leaf of `tree` has one. |
| `evidence` | | Scores of the reading as a whole. |
| `cuts` | yes | One cut per labelled node. |

An inner node is stored only where its contour set differs from the union of its children's.

A cut:

| Property | Required | Value |
|---|---|---|
| `id`, `sig` | yes | 2.7. |
| `path` | yes | Operand indices into the reading's structure. |
| `place` | yes | Where the node stands in its parent: `L`, `C`, `R` under `⿰` and `⿲`; `T`, `M`, `B` under `⿱` and `⿳`; otherwise the operator and the operand index, as `⿸0`. Empty for the root. |
| `component` | yes | Component reference, as the structure writes it (the canonical member). |
| `class` | | The class's canonical member, when the component is in a class. |
| `style` | | `member` (a component reference), `basis` (`kage`, `match`, `cluster` or `hand`), `likeness`, `tier` (`source`, `machine` or `reviewed`). |
| `contours` | yes | Contour indices, ascending. |
| `box` | yes | Box of the cut's contours. |
| `frame` | | Box of the parent node's ink. |
| `gap`, `area`, `ink` | | Distance to the nearest sibling ink, filled area, and summed length of the contours' polygons. |
| `evidence` | | Scores of the cut: `fit` or `match`, `margin`, `agree`, `reference`, and `referenceGlyph`, the glyph `reference` was measured against; `importedFrom`, the project a cut made elsewhere was taken from. |
| `checks` | | Per check: `value`, `limit`, `pass`, and `against`, the glyph compared with. A dealt cut has `filled`, `skeleton`, `windows` and `likeness`, the last per class member; a lifted component has the one that decided it, `reference`, `agree` or `single`. |
| `calibrated` | | The component whose reviewed labels set the checks' limits, or `false`. |
| `division` | yes | `source` for a `kage` division, `machine`, `reviewed` or `hand`. |
| `status` | yes | `accepted`, `refused` (a check failed), `reviewed-right` or `reviewed-wrong`. |

Within a file, a layer has at most one reading under a structure. A subject that is a character
is read on the glyph of its own code point.

Within a reading:

- no path is labelled twice;
- a cut's contours are a subset of the contours of every cut above it on its path, and of the
  layer;
- cuts on different branches share no contour;
- a cut's `component` is the reference of its node in `text` (2.5);
- a `style.member` is in the cut's class.

A skipped attempt holds `subject`, `glyph` when a font draws the subject, `layer`, `structure`,
`text`, and `reason`: a `code` and a sentence `text`.

| Code | Meaning |
|---|---|
| `too-few-pieces` | Fewer pieces than operands. |
| `too-many-pieces` | More pieces than the cutter divides. |
| `unlike-element` | A node is unlike every member of its component's class. |
| `layout-mismatch` | The pieces do not lie as the operator says. |
| `ambiguous` | Two divisions score alike. |
| `does-not-tile` | The pieces do not add up to the glyph. |
| `no-reference-glyph` | No font draws an operand to compare with. |
| `no-enclosure` | No enclosing part was found. |
| `no-face` | No font of the design draws the subject. |
| `no-ink` | The glyph draws nothing. |
| `unlike-whole` | The operands, each drawn where its pieces sit, do not come out as the glyph. |
| `unreadable-structure` | The candidate does not read as a tree. |
| `unlike-division` | GlyphWiki's placed components do not match the structure's operands. |

### 4.4 Form and library files

Both are indexes over cuts and hold no geometry. One file covers one design.

`forms/<design>.json.gz`, `format` `han-decompose/forms@2.0`: `design`, and `forms`, class →
style → the cut chosen as that style's form in that design:

| Property | Required | Value |
|---|---|---|
| `cut`, `sig` | yes | The cut and its signature (2.7). |
| `basis` | yes | What the choice rests on: `reference` (a reference glyph), `agree` (other hosts leave the same shape), `single` (one host whose parts lift away unmistakably), `kage` (a GlyphWiki division), `imported` (the form another project chose, taken over with its cut) or `hand`. |
| `hosts` | | How many hosts gave a cut of the style. |

`library/<design>.json.gz`, `format` `han-decompose/library@2.0`: `design`, and `library`, class
→ style → place (4.3) → cut identifiers, best first. A cut is listed when it confirms the form.

A component that has no character can be read on a host glyph under a structure of its own:
`㇯冐⺜`, 冐 without ⺜, is read on the glyph of 冐. The reading's one cut is the root, which
holds what is left of the host, and its `component` is the structure as a subtree. A
subtraction that several components share is read once, under the first of them.

## 5. Tables

A table is UTF-8 text with tab-separated fields and lines ending in a line feed. Its first line
is `# format=han-decompose/<name>-tsv@2.0`, followed by ` release=<version>` in a release; a
release name holds ASCII letters, digits, `.`, `_`, `+` and `-`. The second line names the columns,
in the order given below. An absent value is empty.

Numbers are written as in the JSON files (section 4).

### 5.1 `cuts`

One row per cut, `cuts.tsv.gz`. Each row stands alone.

| Column | Value |
|---|---|
| `cut_id`, `sig` | 2.7. |
| `font`, `design`, `glyph` | Font, design and glyph selector. |
| `char` | The subject, when it is a character. |
| `layer`, `structure`, `text`, `tree` | As in the reading. |
| `path` | Path as text (2.7). |
| `place` | As in the cut. |
| `depth` | 1 for a node of the glyph's own reading, one more for each layer above it. |
| `whole` | `1` when the node's parent is the root, else `0`. |
| `component`, `class` | As in the cut. |
| `style`, `style_basis`, `style_tier` | From the cut's style. |
| `contours` | Indices separated by spaces. |
| `grain` | From the reading's method. |
| `box`, `frame` | Four numbers separated by spaces. |
| `method`, `tool` | The method's `name` and `tool`. |
| `fit`, `margin`, `agree`, `reference` | From the cut's evidence; `fit` takes `match` where the cut has no `fit`. |
| `filled`, `skeleton` | The checks' values. |
| `calibrated` | A component reference, or `0` for `false`. |
| `division`, `status` | As in the cut. |

The table holds no outline. A reader joins `font`, `glyph` and `contours` to the outline files.

### 5.2 `drawn` and `structures`

`drawn.tsv.gz`, one row per glyph with a drawn IDS: `font`, `design`, `glyph`, `char`, `ids`,
`structure`, `text`, `tier`.

`structures.tsv.gz`, one row per character and structure that fits at least one font: `char`,
`structure`, `text`, `fonts` (font identifiers separated by spaces), `designs`, and `drawn`, the
distinct drawn IDS it takes, separated by spaces.

### 5.3 `classes`

`classes.tsv`, one row per member.

| Column | Value |
|---|---|
| `member` | Component reference. |
| `target` | The component the row resolves it to. |
| `canonical` | Where the rows lead: the class's canonical member. |
| `place` | The place the row applies at (4.3), or empty for every place. |
| `basis` | `unicode-equivalent`, `radical-variant`, `ucv`, `radical-stroke`, `alignment` or `reviewed`. |
| `tier` | `source`, `derived` or `reviewed`. |

A member resolves by following its rows to a component that is no member of anything. A row with a
place applies only there. A member that resolves to two canonical members at one place is in no
class. Components without a row are compared as themselves.

### 5.4 `skipped`

`skipped.tsv.gz`: `font`, `glyph`, `char`, `layer`, `structure`, `text`, `reason_code`, `reason`.

### 5.5 `components`

`components.tsv`, one row per component, or per relation between two.

| Column | Value |
|---|---|
| `component` | Component reference. |
| `kind` | By the reference's kind: `character` (`u`), `subtree` (`ids`), `ledger` (`x`) or `adobe-japan1` (`aj1`). |
| `text` | The component as written (2.4); empty for an Adobe-Japan1 glyph. |
| `relation` | `alias` (another name for it: `{42}`, `&CDP-8958;`, `#(丿𠃊)`), `glyph-of` (a glyph of a character) or `equivalent` (the same shape under another reference). |
| `target` | The other component, or for an alias the name as written. |
| `basis` | What the relation rests on. |
| `tier` | `source` when a table states the relation, `derived` when it is inferred. |

`relation`, `target` and `tier` are filled together or all empty.

### 5.6 `verdicts`

| Column | Value |
|---|---|
| `cut_id`, `sig` | The cut and the contour set judged. |
| `verdict` | `right`, `wrong`, or empty where only a style is named. |
| `style` | The member a reviewer names for the cut, or empty. |
| `note`, `reviewer` | Free text. |
| `at` | `YYYY-MM-DDThh:mm:ssZ`. |
| `release` | The release the cut was seen in. |

A verdict whose `sig` differs from the built cut's applies to nothing.

## 6. Licences

Outline files are under the licence of their font, stated in the file; GlyphWiki's outline files
under GlyphWiki's licence. Every other file is under CC0-1.0.

## 7. Tiers

The outline is the font's. A division is `source` (GlyphWiki's), `machine`, `reviewed` or `hand`;
a style is `source`, `machine` or `reviewed`; a class row or relation is `source`, `derived` or
`reviewed`. Nothing derived is presented as attested.
