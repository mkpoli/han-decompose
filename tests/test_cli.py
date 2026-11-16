from pathlib import Path

import pytest
from typer.testing import CliRunner

from han_decompose import __version__, pins, tsv
from han_decompose.cli import app


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_the_component_table_is_written(tmp_path: Path) -> None:
    try:
        pins.source_paths(pins.source("adobe-japan1"), fetch=False)
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    result = CliRunner().invoke(app, ["components", str(tmp_path)])
    assert result.exit_code == 0 and result.stdout.splitlines() == ["components.tsv\t286"]
    name, _, rows = tsv.read_table((tmp_path / "components.tsv").read_text(encoding="utf-8"))
    assert name == "components" and {row["relation"] for row in rows} == {"glyph-of", "equivalent", ""}
