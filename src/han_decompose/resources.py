"""Where the files that ship with the package are: `schema/` and `pins/`."""

from pathlib import Path


def resource(folder: str) -> Path:
    """A folder of the repository's root, which an installed package carries as `_<folder>`."""
    packaged = Path(__file__).with_name(f"_{folder}")
    return packaged if packaged.exists() else Path(__file__).resolve().parents[2] / folder
