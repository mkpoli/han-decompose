"""The `han-decompose` command."""

from pathlib import Path
from typing import Annotated

import typer

from . import __version__, pins
from . import identifiers as I
from .cutters import survey as surveys
from .importers import composer_export
from .outline import Chain
from .store import Store

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
def survey(
    component: Annotated[str, typer.Argument(help="The component to cut out, as one character.")],
    chain: Annotated[str, typer.Option(help="The font chain to read the glyphs in.")] = "sans",
    source: Annotated[str, typer.Option(help="The description source.")] = "babelstone",
    out: Annotated[Path | None, typer.Option(help="A folder to write outline and cut files into.")] = None,
    workers: Annotated[int, typer.Option(help="How many processes cut at once.")] = 4,
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned files are in.")] = None,
) -> None:
    """Cut one component out of every character whose description reaches it, and count what was
    found: characters read, cuts of the component that passed both checks, cuts refused, and
    characters skipped by reason."""
    store = Store()
    read = accepted = characters = refused = 0
    reasons: dict[str, int] = {}
    try:
        for outcome in surveys.run(component, chain, source, workers, cache):
            for glyph, record in outcome.glyphs.items():
                store.record(*I.split_glyph_id(glyph), record)
            if outcome.reading is not None:
                read += 1
                found = surveys.instances(outcome.reading, component)
                accepted += len(found)
                characters += bool(found)
                refused += sum(
                    cut["text"] == component and cut["status"] == "refused" for cut in outcome.reading["cuts"]
                )
                store.reading(outcome.reading)
            elif outcome.skipped is not None:
                code = outcome.skipped["reason"]["code"]
                reasons[code] = reasons.get(code, 0) + 1
                font = (
                    outcome.skipped["glyph"].split("/")[0] if "glyph" in outcome.skipped else pins.chain(chain)[0]["id"]
                )
                store.skip(outcome.skipped, font)
    except (pins.PinError, KeyError, OSError) as error:
        typer.echo(str(error.args[0]) if isinstance(error, KeyError) else str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(f"read\t{read}")
    typer.echo(f"characters with {component}\t{characters}")
    typer.echo(f"cuts of {component} accepted\t{accepted}")
    typer.echo(f"cuts of {component} refused\t{refused}")
    for code, total in sorted(reasons.items()):
        typer.echo(f"skipped: {code}\t{total}")
    if out is not None:
        typer.echo(f"files\t{len(store.write(out))}\t{out}")
