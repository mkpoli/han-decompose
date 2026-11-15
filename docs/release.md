# Building a release

A release is built on one machine from the pinned inputs, in three steps: cut, build, pack.
Publishing is a fourth step that a person takes.

## 1. Cut

Each command writes a run: a folder of outline and cut files.

```sh
uv run han-decompose fetch
uv run han-decompose lift --chain sans  --out runs/sans.lift
uv run han-decompose lift --chain serif --out runs/serif.lift
uv run han-decompose read runs/sans.babelstone  --chain sans  --source babelstone
uv run han-decompose read runs/serif.babelstone --chain serif --source babelstone
uv run han-decompose read runs/sans.zi-tools    --chain sans  --source zi-tools
uv run han-decompose read runs/serif.zi-tools   --chain serif --source zi-tools
uv run han-decompose read runs/sans.chise       --chain sans  --source chise
uv run han-decompose read runs/serif.chise      --chain serif --source chise
```

`lift` cuts the components no code point names (CHISE entities, zi.tools chains, BabelStone's
numbered components) out of their hosts. `read` deals every glyph to the components of each
description a source gives it. `read` writes one block of 256 code points at a time and leaves a
block alone that is already written, so a run that stopped goes on where it was; `--blocks 04e`
reads single blocks.

A whole table is hours of work on four processes. Run it where it does not starve other work.

## 2. Build

```sh
uv run han-decompose release out/v1.0.0 v1.0.0 \
  --run runs/sans.lift --run runs/serif.lift \
  --run runs/sans.babelstone --run runs/serif.babelstone \
  --run runs/sans.zi-tools --run runs/serif.zi-tools \
  --run runs/sans.chise --run runs/serif.chise \
  --commit "$(git rev-parse --short HEAD)" --dist dist/v1.0.0
```

The runs are merged shard by shard. Where two runs read the same glyph under the same
description, the run given first stands: the lifts go first. Every file is checked against the
schema and the format's invariants, cut files against their outline files; a problem stops the
build. The folder then holds the layout of `docs/format.md`: outlines, cuts, the form and library
indexes, the flat tables per source, the component tables, `fonts.json` and `sources.json`, the
licence texts, a `README.md` that names every font and source with its terms, `manifest.json`
and `SHA256SUMS`.

`--dist` packs it for a release page: one archive of outlines per font, one of cuts per font and
source, the indexes and licence texts as archives, and the tables, registries, README, manifest
and checksums as they are. The same release packs to the same bytes.

## 3. Publish

The build publishes nothing. After the release has been looked at:

```sh
git tag v1.0.0 && git push origin v1.0.0
gh release create v1.0.0 dist/v1.0.0/* --title "han-decompose data v1.0.0" --notes-file out/v1.0.0/README.md
```

## Versions

`vMAJOR.MINOR.PATCH`. MAJOR follows the format's major version. MINOR is a change in fonts,
sources or cutters. PATCH is verdicts and statuses only. A release that covers part of the tables
says so in its README.
