# han-decompose

han-decompose records, for each Han character a font draws, which of the glyph's contours belong
to which component of its ideographic description sequence (IDS). Every part is a set of contours
the font already draws.

Its sibling [han-compose](https://github.com/mkpoli/han-compose) draws a character from its
description.

## Format

[docs/format.md](docs/format.md) defines the files and their identifiers;
`schema/1/han-decompose.schema.json` is the same definition as JSON Schema.
[docs/parity.md](docs/parity.md) records the check that contours are counted as han-compose counts
them. [docs/reproduction.md](docs/reproduction.md) holds the cutters against the ids-input data they came
from.

## Licences

Code is under the MIT licence (`LICENSE`).

Data files are outside it. Each data file keeps the licence of the font its outlines come from and
lists the terms of the description sources its labels were read from.
[docs/licensing.md](docs/licensing.md) says which terms reach which file.

## Sources

[pins/README.md](pins/README.md) cites every font and table a build reads, with its version,
SHA-256 and licence. `uv run han-decompose fetch` downloads them into `~/.cache/han-decompose` and
checks each digest.

## Development

The builder is a Python package managed with [uv](https://docs.astral.sh/uv/); the reader for
JavaScript is the npm package in `packages/format`, managed with [bun](https://bun.sh/).

```sh
uv sync
uv run pytest         # unit tests
uv run mypy           # type check
uv run ruff check     # lint
uv build

bun install
bun test
bun run typecheck
bun run build
```
