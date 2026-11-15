"""The `han-decompose` command."""

from pathlib import Path
from typing import Annotated

import typer

from . import __version__, aj1, pins, tsv
from .importers import composer_export
from .outline import Chain

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Print the version and exit.")
    ] = False,
) -> None:
    """Which contours of a font's Han glyph belong to which component of its description."""


@app.command()
def fetch(
    names: Annotated[
        list[str] | None, typer.Argument(help="Font or source identifiers; all when none is given.")
    ] = None,
    cache: Annotated[
        Path | None, typer.Option(help=f"The cache folder; ${pins.ENV_CACHE} or ~/.cache/han-decompose.")
    ] = None,
) -> None:
    """Fetch the pinned fonts and source tables into the cache and check each against its SHA-256."""
    try:
        for identifier, path in pins.fetch_all(set(names) if names else None, cache):
            typer.echo(f"{identifier}\t{path}")
    except (pins.PinError, KeyError, OSError) as error:
        typer.echo(str(error.args[0]) if isinstance(error, KeyError) else str(error), err=True)
        raise typer.Exit(1) from error


@app.command()
def citations() -> None:
    """Print `pins/README.md`: every pinned font and source with its version, digest and terms."""
    typer.echo(pins.citations(), nl=False)


@app.command()
def parity(
    export: Annotated[Path, typer.Argument(help="A han-compose web export folder.")],
    chain: Annotated[str, typer.Option(help="The font chain the export was written from.")] = "sans",
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned fonts are in.")] = None,
) -> None:
    """Check that every glyph record of a han-compose export is the outline read here from the
    same fonts: the same contours in the same order, point for point on the export's grid."""
    try:
        with Chain.pinned(chain, cache) as fonts:
            result = composer_export.parity(export, fonts)
    except (pins.PinError, KeyError, ValueError, OSError) as error:
        typer.echo(str(error.args[0]) if isinstance(error, KeyError) else str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(f"shards\t{result.shards}\tof {result.stated[0]}")
    typer.echo(f"records\t{result.records}\tof {result.stated[1]}")
    typer.echo(f"glyph records\t{result.glyphs}")
    typer.echo(f"compared\t{result.compared}")
    typer.echo(f"identical\t{result.same}")
    typer.echo(f"different\t{len(result.different)}\t{' '.join(result.different[:20])}")
    typer.echo(f"from another font\t{len(result.other_face)}\t{' '.join(result.other_face[:20])}")
    if not result.exact:
        raise typer.Exit(1)


@app.command()
def components(
    out: Annotated[Path, typer.Argument(help="A folder to write the component tables into.")],
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned files are in.")] = None,
) -> None:
    """Write the component tables, one per source: the Adobe-Japan1 glyphs CHISE's descriptions
    name, each with the character Adobe's kanji table makes it a glyph of."""
    try:
        rows = aj1.pinned(cache)
    except (pins.PinError, ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    out.mkdir(parents=True, exist_ok=True)
    for source in sorted({row["source"] for row in rows}):
        mine = [row for row in rows if row["source"] == source]
        (out / f"components.{source}.tsv").write_text(tsv.write_table("components", mine), encoding="utf-8")
        typer.echo(f"components.{source}.tsv\t{len(mine)}")
