from typer.testing import CliRunner

from han_decompose import __version__
from han_decompose.cli import app


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
