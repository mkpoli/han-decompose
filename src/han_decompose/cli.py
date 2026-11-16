"""The `han-decompose` command."""

from pathlib import Path
from typing import Annotated

import typer

from . import __version__, aj1, pins, tsv
from . import identifiers as I
from .cutters import library as libraries
from .cutters import survey as surveys
from .importers import composer_export
from .outline import Chain
from .release import Release, pack
from .schema import Json
from .store import Store

#: The designs glyphs are read in when none is named: Source Han Sans, then Plangothic where it lacks one.
DESIGNS = ["source-han-sans", "plangothic"]

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
    design: Annotated[
        list[str] | None, typer.Option(help="A design of the fonts the export was written from, in order.")
    ] = None,
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned fonts are in.")] = None,
) -> None:
    """Check that every glyph record of a han-compose export is the outline read here from the
    same fonts: the same contours in the same order, point for point on the export's grid."""
    try:
        with Chain.pinned(design or DESIGNS, cache) as fonts:
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
    design: Annotated[
        list[str] | None, typer.Option(help="A design whose fonts the glyphs are read in, in order of preference.")
    ] = None,
    source: Annotated[str, typer.Option(help="The description source.")] = "babelstone",
    out: Annotated[Path | None, typer.Option(help="A folder to write outline and cut files into.")] = None,
    workers: Annotated[int, typer.Option(help="How many processes cut at once.")] = 4,
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned files are in.")] = None,
) -> None:
    """Cut one component out of every character whose description reaches it, and count what was
    found: characters read, cuts of the component that passed both checks, cuts refused, and
    characters skipped by reason."""
    if out is not None and out.exists() and any(out.iterdir()):
        typer.echo(f"{out} is not empty.", err=True)
        raise typer.Exit(1)
    designs = design or DESIGNS
    store = Store()
    read = accepted = characters = refused = 0
    reasons: dict[str, int] = {}
    try:
        for outcome in surveys.run(component, designs, source, workers, cache):
            for glyph, record in outcome.glyphs.items():
                store.record(*I.split_glyph_id(glyph), record)
            if outcome.readings is not None:
                read += 1
                found = surveys.instances(outcome.readings, component)
                accepted += len(found)
                characters += bool(found)
                refused += sum(
                    cut["class"] == I.component_of(component) and cut["status"] == "refused"
                    for row in outcome.readings
                    for cut in row["cuts"]
                )
                for row in outcome.readings:
                    store.reading(row)
            elif outcome.skipped is not None:
                code = outcome.skipped["reason"]["code"]
                reasons[code] = reasons.get(code, 0) + 1
                font = (
                    outcome.skipped["glyph"].split("/")[0]
                    if "glyph" in outcome.skipped
                    else pins.chain(designs[0])[0]["id"]
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


@app.command()
def read(
    out: Annotated[Path, typer.Argument(help="A folder to write the outline and cut files into.")],
    design: Annotated[
        list[str] | None, typer.Option(help="A design whose fonts the glyphs are read in, in order of preference.")
    ] = None,
    source: Annotated[str, typer.Option(help="The description source.")] = "babelstone",
    workers: Annotated[int, typer.Option(help="How many processes cut at once.")] = 4,
    blocks: Annotated[list[str] | None, typer.Option(help="Blocks of 256 code points to read, as `04e`.")] = None,
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned files are in.")] = None,
) -> None:
    """Read every description of a source in a design: each glyph dealt to the components of its
    description, and deeper where they can be told apart. A block already written under the
    folder is left as it is, so a run that stopped goes on where it was."""
    designs = design or DESIGNS
    total = libraries.Counts()
    try:
        for block, counts in libraries.run(designs, source, out, workers, cache, blocks):
            total.add(counts)
            typer.echo(f"{block}\t{counts.readings}\t{sum(counts.skipped.values())}", err=True)
        added = libraries.named(out, designs, cache)
    except (pins.PinError, KeyError, OSError) as error:
        typer.echo(str(error.args[0]) if isinstance(error, KeyError) else str(error), err=True)
        raise typer.Exit(1) from error
    summary = total.summary()
    typer.echo(f"readings\t{summary['readings']}")
    for status, number in summary["cuts"].items():
        typer.echo(f"cuts {status}\t{number}\tof {summary['components'][status]} components")
    for code, number in summary["skipped"].items():
        typer.echo(f"skipped: {code}\t{number}")
    typer.echo(f"reference outlines added\t{added}")


def component_rows(cache: Path | None) -> list[Json]:
    """The rows of the component table: the Adobe-Japan1 glyphs that descriptions name."""
    return aj1.pinned(cache)


@app.command()
def release(
    out: Annotated[Path, typer.Argument(help="An empty folder to build the release in.")],
    version: Annotated[str, typer.Argument(help="The release's name, as `v1.0.0`.")],
    run: Annotated[
        list[Path], typer.Option(help="A folder of outline and cut files; the first given takes precedence.")
    ],
    dist: Annotated[
        Path | None, typer.Option(help="A folder to pack the release into, one archive per font and kind.")
    ] = None,
    commit: Annotated[str | None, typer.Option(help="The commit the runs were made from.")] = None,
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned files are in.")] = None,
) -> None:
    """Build a data release from cutting runs: their files merged and checked, the flat tables, the
    registry, a README with every font and licence, the licence texts, a manifest and checksums.
    Nothing is published."""
    try:
        built = Release(out, version)
        built.shards(run)
        built.indexes()
        built.flat(component_rows(cache))
        manifest = built.finish(commit)
    except (pins.PinError, ValueError, KeyError, OSError) as error:
        typer.echo(str(error.args[0]) if isinstance(error, KeyError) else str(error), err=True)
        raise typer.Exit(1) from error
    for problem in built.problems[:50]:
        typer.echo(problem, err=True)
    typer.echo(f"files\t{len(manifest['files'])}")
    for font, count in manifest["counts"].items():
        cuts = " ".join(f"{status} {number}" for status, number in count["cuts"].items())
        typer.echo(f"{font}\treadings {count['readings']}\t{cuts}\tclasses {count['classes']}")
    if built.problems:
        typer.echo(f"problems\t{len(built.problems)}", err=True)
        raise typer.Exit(1)
    if dist is not None:
        try:
            typer.echo(f"assets\t{len(pack(out, dist))}\t{dist}")
        except ValueError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(1) from error


@app.command()
def components(
    out: Annotated[Path, typer.Argument(help="A folder to write the component table into.")],
    cache: Annotated[Path | None, typer.Option(help="The cache folder the pinned files are in.")] = None,
) -> None:
    """Write the component table: each Adobe-Japan1 glyph that descriptions name, with the
    character Adobe's kanji table makes it a glyph of."""
    try:
        rows = component_rows(cache)
    except (pins.PinError, ValueError, KeyError, OSError) as error:
        typer.echo(str(error.args[0]) if isinstance(error, KeyError) else str(error), err=True)
        raise typer.Exit(1) from error
    out.mkdir(parents=True, exist_ok=True)
    (out / "components.tsv").write_text(tsv.write_table("components", rows), encoding="utf-8")
    typer.echo(f"components.tsv\t{len(rows)}")
