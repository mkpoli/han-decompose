"""The `han-decompose` command."""

from typing import Annotated

import typer

from . import __version__

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
