"""GlyphWiki as a glyph source: the dump, and its glyphs drawn by the KAGE engine.

The drawing runs in `packages/kage` (bun). Contours are in KAGE's frame: 200 units, y down.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from han_decompose import pins
from han_decompose.schema import Json

DUMP_URL = "https://glyphwiki.org/dump.tar.gz"
DUMP_MEMBER = "dump_newest_only.txt"
VERSIONS_MEMBER = "dump_all_versions.txt"
VERSIONS_USED = "versions_used.txt"
KAGE_CLI = Path(__file__).resolve().parents[2] / "packages" / "kage" / "src" / "cli.ts"
UPEM = 200


# --- the dump -----------------------------------------------------------------------------


def cache_dir(cache: Path | None = None) -> Path:
    return (cache or pins.cache_root()) / "glyphwiki"


def parse_dump_line(line: str) -> tuple[str, str] | None:
    """`name | related | data` of GlyphWiki's psql-style dump, or None for header, rule and count."""
    first = line.find("|")
    second = line.find("|", first + 1) if first >= 0 else -1
    if second < 0:
        return None
    name = line[:first].strip()
    if name in ("", "name") or name.startswith("---"):
        return None
    return name, line[second + 1 :].strip()


def read_dump(path: Path) -> dict[str, str]:
    """Name → KAGE data. The `related` column is not read."""
    glyphs: dict[str, str] = {}
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if row := parse_dump_line(line):
                glyphs[row[0]] = row[1]
    return glyphs


def pinned_versions(glyphs: dict[str, str]) -> set[str]:
    """Names of the form `u5927-04@2` that glyph data places: a version of a glyph, which the
    newest-only dump does not hold."""
    wanted: set[str] = set()
    for data in glyphs.values():
        if "@" not in data:
            continue
        for line in data.split("$"):
            columns = line.split(":")
            if columns[0] == "99" and len(columns) > 7 and "@" in columns[7]:
                wanted.add(columns[7])
    return wanted


def extract_versions(all_versions: Path, newest: dict[str, str], out: Path) -> int:
    """Write the versions that glyph data pins, and those they pin in turn, to `out` in the dump's
    layout. `dump_all_versions.txt` names a version `name\\@N`; the data places it as `name@N`."""
    found: dict[str, str] = {}
    wanted = pinned_versions(newest)
    while pending := wanted - found.keys():
        before = len(found)
        with all_versions.open(encoding="utf-8") as lines:
            for line in lines:
                row = parse_dump_line(line)
                if row is not None and (name := row[0].replace("\\@", "@")) in pending:
                    found[name] = row[1]
        if len(found) == before:
            break  # what is left is not in the dump
        wanted |= pinned_versions(found)
    with out.open("w", encoding="utf-8") as sink:
        for name in sorted(found):
            sink.write(f" {name} | | {found[name]}\n")
    return len(found)


def read_names(path: Path) -> list[str]:
    """Only the glyph names of a dump file, which takes a fraction of the memory `read_dump` does."""
    with path.open(encoding="utf-8") as lines:
        return [
            name
            for line in lines
            if (name := line.partition("|")[0].strip()) not in ("", "name")
            and "|" in line
            and not name.startswith("---")
        ]


@dataclass(frozen=True)
class Dump:
    path: Path
    url: str
    size: int
    sha256: str
    modified: str
    """The archive's Last-Modified, in GMT, as an ISO time."""

    @property
    def versions(self) -> Path:
        """The versions the glyph data pins (`u5927-04@2`), which `path` lacks."""
        return self.path.with_name(VERSIONS_USED)

    @property
    def date(self) -> str:
        """YYYYMMDD of the archive's Last-Modified (GMT), the `glyphwiki@<date>` of the font row."""
        return self.modified[:10].replace("-", "")


def fetch_dump(cache: Path | None = None, url: str = DUMP_URL) -> Dump:
    """Download the dump once into the cache. A second call reads the record it left."""
    folder = cache_dir(cache)
    record = folder / "dump.json"
    member = folder / "dump" / DUMP_MEMBER
    if record.exists() and member.exists() and member.with_name(VERSIONS_USED).exists():
        row = json.loads(record.read_text(encoding="utf-8"))
        return Dump(member, row["url"], row["size"], row["sha256"], row["modified"])
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "dump.tar.gz"
    digest = hashlib.sha256()
    with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
        response.raise_for_status()
        modified = parsedate_to_datetime(response.headers["last-modified"]).astimezone(UTC)
        with archive.open("wb") as out:
            for chunk in response.iter_bytes(1 << 20):
                digest.update(chunk)
                out.write(chunk)
    (folder / "dump").mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extract(tar.getmember(DUMP_MEMBER), folder / "dump", filter="data")
        for extra in ("LICENSE.txt", "README_en.txt", VERSIONS_MEMBER):
            tar.extract(tar.getmember(extra), folder / "dump", filter="data")
    all_versions = folder / "dump" / VERSIONS_MEMBER
    extract_versions(all_versions, read_dump(member), member.with_name(VERSIONS_USED))
    all_versions.unlink()
    row = {
        "url": url,
        "size": archive.stat().st_size,
        "sha256": digest.hexdigest(),
        "modified": modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    record.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return Dump(member, row["url"], row["size"], row["sha256"], row["modified"])


# --- names → characters --------------------------------------------------------------------

_NAME = re.compile(r"u([0-9a-f]{4,6})(?:-(.*))?\Z")
_SELECTOR = re.compile(r"u(fe0[0-9a-f]|e01[0-9a-f]{2})(?:-(.*))?\Z")
_CJK = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2EE5D),
    (0x2F800, 0x2FA1F),
    (0x30000, 0x3347F),
)


def is_cjk(code_point: int) -> bool:
    """A Han ideograph of the Unified, Extension or Compatibility blocks."""
    return any(low <= code_point <= high for low, high in _CJK)


@dataclass(frozen=True)
class NameInfo:
    code_point: int
    selector: int | None = None
    """The variation selector of an IVS glyph (`u845b-ue0100`)."""
    suffix: str | None = None
    """What follows in the name: `j`, `01`, `var-002`; None for the bare glyph."""

    @property
    def selector_spelling(self) -> str:
        """`U+845B` or `U+845B.E0100`, the selector of format 2."""
        base = f"U+{self.code_point:04X}"
        return base if self.selector is None else f"{base}.{self.selector:04X}"


def name_info(name: str) -> NameInfo | None:
    """The code point a GlyphWiki name starts with: `uXXXX`, `uXXXX-suffix`, `uXXXX-uE01XX[-suffix]`.

    The name decides. A glyph whose name holds no code point (`cdp-…`, `koseki-…`) has none.
    """
    found = _NAME.match(name)
    if found is None:
        return None
    code_point = int(found.group(1), 16)
    if code_point > 0x10FFFF or 0xD800 <= code_point <= 0xDFFF:
        return None
    rest = found.group(2)
    if rest is not None and (sel := _SELECTOR.match(rest if rest.startswith("u") else "")):
        return NameInfo(code_point, int(sel.group(1), 16), sel.group(2))
    return NameInfo(code_point, None, rest)


def cjk_names(names: Iterable[str]) -> Iterator[str]:
    """The names that map to a Han code point, or to an IVS of one."""
    for name in names:
        info = name_info(name)
        if info is not None and is_cjk(info.code_point):
            yield name


# --- drawing -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Stroke:
    type: int
    contours: tuple[int, ...]
    """Indices into `Drawing.contours`."""


@dataclass(frozen=True)
class Placement:
    id: int
    glyph: str
    parent: int | None
    depth: int
    box: tuple[float, float, float, float]
    """The placed glyph's cell, stretched as the engine stretches it; see `ink` for what was drawn."""
    ink: tuple[float, float, float, float] | None
    """Extent of the polygons the placement drew: min x, min y, max x, max y."""
    strokes: tuple[int, ...]
    contours: tuple[int, ...]


@dataclass(frozen=True)
class Contour:
    points: tuple[tuple[float, float], ...]
    stroke: int
    placements: tuple[int, ...]
    """Every placement that contains the contour, outermost first."""


@dataclass(frozen=True)
class Drawing:
    name: str
    contours: tuple[Contour, ...]
    strokes: tuple[Stroke, ...]
    placements: tuple[Placement, ...]
    alias: str | None
    missing: tuple[str, ...]

    def leaves(self) -> tuple[Placement, ...]:
        """The innermost placements, which place a glyph that is not itself a list of placements."""
        parents = {p.parent for p in self.placements}
        return tuple(p for p in self.placements if p.id not in parents)


@dataclass(frozen=True)
class Failure:
    name: str
    reason: str
    message: str


def parse_drawing(row: Json) -> Drawing:
    contours: list[Contour] = []
    strokes: list[Stroke] = []
    owners: dict[int, list[int]] = {}
    placements_raw: list[Json] = row["placements"]
    for index, stroke in enumerate(row["strokes"]):
        first = len(contours)
        for polygon in stroke["polygons"]:
            contours.append(Contour(tuple((x, y) for x, y in polygon), index, ()))
        strokes.append(Stroke(stroke["type"], tuple(range(first, len(contours)))))
    placements: list[Placement] = []
    for pid, p in enumerate(placements_raw):
        a, b = p["strokes"]
        c, d = p["polygons"]
        placements.append(
            Placement(
                pid,
                p["glyph"],
                p["parent"],
                p["depth"],
                tuple(p["box"]),
                tuple(p["ink"]) if p["ink"] else None,
                tuple(range(a, b)),
                tuple(range(c, d)),
            )
        )
        for k in range(c, d):
            owners.setdefault(k, []).append(pid)
    contours = [Contour(c.points, c.stroke, tuple(owners.get(k, ()))) for k, c in enumerate(contours)]
    return Drawing(row["name"], tuple(contours), tuple(strokes), tuple(placements), row["alias"], tuple(row["missing"]))


def _bun() -> str:
    found = shutil.which("bun") or shutil.which("bun", path=str(Path.home() / ".bun" / "bin"))
    if found is None:
        raise RuntimeError("bun is needed to run the KAGE engine")
    return found


def draw_rows(names: Iterable[str], dump: Path | Dump, workers: int = 1) -> Iterator[Json]:
    """JSON rows from `packages/kage`, one per name: a drawing, or `{name, error}`. At most 4 workers."""
    names = list(names)
    workers = max(1, min(workers, 4, len(names)))
    files = [dump.path, dump.versions] if isinstance(dump, Dump) else [dump]
    dump_args = [arg for f in files if f.exists() for arg in ("--dump", str(f))]
    with tempfile.TemporaryDirectory() as tmp:
        procs: list[subprocess.Popen[str]] = []
        for k in range(workers):
            part = Path(tmp) / f"names-{k}.txt"
            part.write_text("\n".join(names[k::workers]) + "\n", encoding="utf-8")
            procs.append(
                subprocess.Popen(
                    [_bun(), str(KAGE_CLI), *dump_args, "--list", str(part)],
                    stdout=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
            )
        try:
            if workers == 1:
                yield from (json.loads(line) for line in procs[0].stdout or ())
            else:
                yield from _merge(procs)
            for proc in procs:
                if proc.wait() != 0:
                    raise RuntimeError(f"the KAGE worker exited with {proc.returncode}")
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()


def _merge(procs: list[subprocess.Popen[str]]) -> Iterator[Json]:
    import queue

    lines: queue.Queue[str | None] = queue.Queue(maxsize=512)

    def pump(proc: subprocess.Popen[str]) -> None:
        for line in proc.stdout or ():
            lines.put(line)
        lines.put(None)

    threads = [threading.Thread(target=pump, args=(proc,), daemon=True) for proc in procs]
    for thread in threads:
        thread.start()
    done = 0
    while done < len(procs):
        line = lines.get()
        if line is None:
            done += 1
        else:
            yield json.loads(line)


def draw(names: Iterable[str], dump: Path | Dump, workers: int = 1) -> Iterator[Drawing | Failure]:
    """The drawings of `names`, read from the dump: its text file, or a `Dump` with the pinned versions."""
    for row in draw_rows(names, dump, workers):
        if "error" in row:
            yield Failure(row["name"], row["error"]["reason"], row["error"]["message"])
        else:
            yield parse_drawing(row)


# --- the batch run -------------------------------------------------------------------------


@dataclass
class BatchResult:
    drawn: int = 0
    failures: dict[str, int] = field(default_factory=dict)
    examples: dict[str, list[str]] = field(default_factory=dict)
    with_missing: int = 0
    raw_bytes: int = 0


def batch(output: Path, dump: Dump, workers: int = 2) -> BatchResult:
    """Draw every glyph whose name maps to a Han code point, to gzip-compressed JSON lines."""
    names = sorted(cjk_names(read_names(dump.path)))
    result = BatchResult()
    with gzip.open(output, "wt", encoding="utf-8", compresslevel=6) as out:
        for row in draw_rows(names, dump, workers):
            if "error" in row:
                reason = row["error"]["reason"]
                result.failures[reason] = result.failures.get(reason, 0) + 1
                if len(result.examples.setdefault(reason, [])) < 5:
                    result.examples[reason].append(row["name"])
            else:
                result.drawn += 1
                result.with_missing += bool(row["missing"])
            line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            result.raw_bytes += len(line) + 1
            out.write(line + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["fetch"]:
        dump = fetch_dump()
        print(f"{dump.path} {dump.date} {dump.size} {dump.sha256}")
        return 0
    if args[:1] == ["batch"]:
        dump = fetch_dump()
        output = cache_dir() / f"glyphwiki-{dump.date}.jsonl.gz"
        started = datetime.now()
        result = batch(output, dump)
        seconds = (datetime.now() - started).total_seconds()
        print(
            json.dumps({"output": str(output), "bytes": output.stat().st_size, "seconds": seconds, **result.__dict__})
        )
        return 0
    print("usage: python -m han_decompose.glyphwiki fetch | batch", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
