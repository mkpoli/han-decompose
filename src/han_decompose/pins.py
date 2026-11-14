"""The pinned inputs: fonts and source tables, fetched once into a cache and checked against
their SHA-256.

`pins/fonts.json` and `pins/sources.json` are the registries. A path is handed out only after the
file at it has been hashed in that call and found to be the pinned bytes; a file that differs stops
the build.
"""

import hashlib
import json
import os
import zipfile
from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from .resources import resource
from .schema import Json, validate

ENV_CACHE = "HAN_DECOMPOSE_CACHE"

Download = Callable[[str], bytes]


class PinError(ValueError):
    """A file that is missing, or whose bytes are not the pinned ones."""


def cache_root() -> Path:
    """Where fetched files are kept: `$HAN_DECOMPOSE_CACHE`, else `han-decompose` under
    `$XDG_CACHE_HOME` or `~/.cache`."""
    if override := os.environ.get(ENV_CACHE):
        return Path(override)
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "han-decompose"


@cache
def fonts() -> Json:
    """The font registry, `pins/fonts.json`."""
    value: Json = json.loads((resource("pins") / "fonts.json").read_text(encoding="utf-8"))
    validate("fonts", value)
    return value


@cache
def sources() -> Json:
    """The source registry, `pins/sources.json`."""
    value: Json = json.loads((resource("pins") / "sources.json").read_text(encoding="utf-8"))
    validate("sources", value)
    return value


def font(identifier: str) -> Json:
    """The registry row of a font."""
    for row in fonts()["fonts"]:
        if row["id"] == identifier:
            return dict(row)
    raise KeyError(f"{identifier} is not a pinned font.")


def source(identifier: str) -> Json:
    """The registry row of a source."""
    for row in sources()["sources"]:
        if row["id"] == identifier:
            return dict(row)
    raise KeyError(f"{identifier} is not a pinned source.")


def chain(name: str) -> list[Json]:
    """The fonts of a chain, in the order a glyph is looked for."""
    if name not in fonts()["chains"]:
        raise KeyError(f"{name} is not a font chain.")
    return [font(identifier) for identifier in fonts()["chains"][name]]


class DownloadError(OSError):
    """An address that did not answer with a file."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download(url: str) -> bytes:
    import httpx

    try:
        response = httpx.get(url, follow_redirects=True, timeout=httpx.Timeout(600, connect=30))
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise DownloadError(str(error)) from error
    return response.content


def _inside(folder: Path, name: str) -> Path:
    """`folder/name` for a plain file name; a name that would leave the folder is refused."""
    if not name or Path(name).name != name or name in (".", ".."):
        raise PinError(f"{name!r} is not a file name.")
    return folder / name


def _write(path: Path, data: bytes) -> None:
    """Write a file whole: a reader sees the old state or the new, never part of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{os.getpid()}.part")
    try:
        partial.write_bytes(data)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def _check(path: Path, sha256: str) -> None:
    with path.open("rb") as file:
        if hashlib.file_digest(file, "sha256").hexdigest() != sha256:
            raise PinError(f"{path} does not match its pinned SHA-256 {sha256}. Remove it to fetch it again.")


def _pinned(path: Path, sha256: str, urls: list[str], fetch: bool, download: Download) -> None:
    """Make `path` hold the bytes pinned by `sha256`: checked where it exists, else fetched from
    the first of `urls` that serves them."""
    if path.exists():
        return _check(path, sha256)
    if not fetch:
        raise PinError(f"{path} is not in the cache. Run `han-decompose fetch`.")
    failures = []
    for url in urls:
        try:
            data = download(url)
        except OSError as error:
            failures.append(f"{url}: {error}")
            continue
        if _digest(data) == sha256:
            return _write(path, data)
        failures.append(f"{url}: SHA-256 {_digest(data)}, pinned {sha256}")
    raise PinError(f"No address serves the pinned bytes of {path.name}.\n" + "\n".join(failures))


def font_path(row: Json, cache: Path | None = None, fetch: bool = True, download: Download = _download) -> Path:
    """The font file of a registry row under `<cache>/fonts`, its digest checked. A font that is a
    member of an archive is extracted from it; the archive is kept beside it, named by its digest,
    and checked too."""
    folder = (cache or cache_root()) / "fonts"
    path = _inside(folder, row["file"])
    if "archive" in row and not path.exists():
        pinned = row["archive"]["sha256"]
        archive = _inside(folder, f"{pinned[:16]}-{Path(urlsplit(row['url']).path).name}")
        _pinned(archive, pinned, [row["url"]], fetch, download)
        try:
            with zipfile.ZipFile(archive) as packed:
                member = packed.read(row["archive"]["member"])
        except KeyError as error:
            raise PinError(f"{row['url']} holds no {row['archive']['member']}.") from error
        if _digest(member) != row["sha256"]:
            raise PinError(f"{row['archive']['member']} of {row['url']} does not match its pinned SHA-256.")
        _write(path, member)
    _pinned(path, row["sha256"], [row["url"]], fetch, download)
    return path


def source_paths(
    row: Json, cache: Path | None = None, fetch: bool = True, download: Download = _download
) -> dict[str, Path]:
    """The files of a source's registry row under `<cache>/sources/<id>`, by name, digests checked."""
    folder = _inside((cache or cache_root()) / "sources", row["id"])
    out = {}
    for file in row.get("files", ()):
        path = _inside(folder, file["file"])
        _pinned(path, file["sha256"], [file["url"], *file.get("mirrors", ())], fetch, download)
        out[file["file"]] = path
    return out


def fetch_all(
    only: set[str] | None = None, cache: Path | None = None, download: Download = _download
) -> Iterator[tuple[str, Path]]:
    """Fetch and check every pinned file, or those of the fonts and sources named in `only`:
    each identifier with a file of its own. A font or source that fails does not stop the others;
    the failures are raised together once every one has been tried."""
    known = {row["id"] for row in fonts()["fonts"]} | {row["id"] for row in sources()["sources"]}
    if only is not None and only - known:
        raise KeyError(f"Not pinned: {', '.join(sorted(only - known))}.")
    failures = []
    for row in fonts()["fonts"]:
        if only is None or row["id"] in only:
            try:
                yield row["id"], font_path(row, cache, download=download)
            except PinError as error:
                failures.append(f"{row['id']}: {error}")
    for row in sources()["sources"]:
        if only is None or row["id"] in only:
            try:
                for path in source_paths(row, cache, download=download).values():
                    yield row["id"], path
            except PinError as error:
                failures.append(f"{row['id']}: {error}")
    if failures:
        raise PinError("\n".join(failures))
