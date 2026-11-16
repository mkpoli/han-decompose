# Building a release

A release is built on one machine from the pinned inputs, in three steps: cut, build, pack.
Publishing is a fourth step that a person takes.

## 1. Cut

Each command writes a run: a folder of outline and cut files.

```sh
uv run han-decompose fetch
uv run han-decompose read runs/babelstone --source babelstone
uv run han-decompose read runs/chise      --source chise
uv run han-decompose read runs/zi-tools   --source zi-tools
```

`read` deals every glyph to the components of each description a source gives it, in the fonts of
the designs named with `--design` (`source-han-sans`, then `plangothic`, by default). It writes one
block of 256 code points at a time and leaves a block alone that is already written, so a run that
stopped goes on where it was; `--blocks 04e` reads single blocks. A description that names a
component no ledger identifier covers (`{42}`, `&CDP-8958;`, `#(丿𠃊)`) is skipped as unreadable until
phase 9 of [`design.md`](design.md) reads candidates in the notation of format 2.

A whole table is hours of work on four processes. Run it where it does not starve other work.

## 2. Build

```sh
uv run han-decompose release out/v2.0.0 v2.0.0 \
  --run runs/babelstone --run runs/chise --run runs/zi-tools \
  --commit "$(git rev-parse --short HEAD)" --dist dist/v2.0.0
```

The runs are merged shard by shard. Where two runs read the same layer under the same structure by
the same method, the run given first stands. Every file is checked against the schema and the
format's invariants, cut files against their outline files. Problems are listed, the command fails,
and nothing is packed. The folder then holds the layout of `docs/format.md`: outlines, strokes and
cuts per font, the form and library indexes per design, the flat tables, `fonts.json`, the licence
texts, a `README.md` that names every font with its terms, `manifest.json` and `SHA256SUMS`.

`--dist` packs it for a release page: one archive of outlines, one of strokes and one of cuts per
font, the indexes and licence texts as archives, and the tables, registry, README, manifest and
checksums as they are. The same release packs to the same bytes.

## 3. Publish

The build publishes nothing. After the release has been looked at:

```sh
git tag v2.0.0 && git push origin v2.0.0
gh release create v2.0.0 dist/v2.0.0/* --title "han-decompose data v2.0.0" --notes-file out/v2.0.0/README.md
```

## Versions

`vMAJOR.MINOR.PATCH`. MAJOR follows the format's major version. MINOR is a change in fonts,
sources or cutters. PATCH is verdicts and statuses only. A release that covers part of the tables
says so in its README.
