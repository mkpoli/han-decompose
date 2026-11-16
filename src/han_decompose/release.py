"""Build a data release: the shards of several cutting runs merged into the one layout
`docs/format.md` gives, with the flat tables, the registry, a README that names every font and
licence, the licence texts, a manifest and checksums; then packed as one archive per font and kind
for the release page.

A run's folder holds `outlines/`, `strokes/` and `cuts/` shards, and may hold `forms/` and
`library/`. Runs are given in order of precedence: where two hold a reading of the same layer under
the same structure by the same method, the earlier run's stands.
"""

import gzip
import hashlib
import io
import json
import shutil
import tarfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from . import __version__, pins, tsv
from . import identifiers as I
from .resources import resource
from .schema import Json, problems
from .store import FORMS, LIBRARY, MANIFEST, choose, dumps, write

ACCEPTED = ("accepted", "reviewed-right")


def _load(path: Path) -> Json:
    value: Json = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())
    return value


def _shards(runs: Sequence[Path], top: str) -> dict[str, list[Path]]:
    """Every shard under `top` of every run, by its path in the release, runs in order."""
    out: dict[str, list[Path]] = {}
    for run in runs:
        if not run.is_dir():
            raise ValueError(f"{run} is not the folder of a run.")
        for path in sorted((run / top).rglob("*.json.gz")) if (run / top).is_dir() else []:
            out.setdefault(path.relative_to(run).as_posix(), []).append(path)
    return dict(sorted(out.items()))


def merge_outlines(paths: Sequence[Path]) -> Json:
    """One outline file from the same shard of several runs. A glyph two runs hold is one glyph."""
    merged = _load(paths[0])
    for path in paths[1:]:
        for selector, record in _load(path)["glyphs"].items():
            if merged["glyphs"].setdefault(selector, record) != record:
                raise ValueError(f"{path}: {selector} differs from an earlier run's.")
    merged["glyphs"] = dict(sorted(merged["glyphs"].items(), key=lambda item: I.order(item[0])))
    return merged


def _key(row: Json) -> tuple[tuple[int, int, int, str], str, list[str], str]:
    selector = I.split_glyph_id(row["glyph"])[1] if "glyph" in row else "gid.0"
    return (I.order(selector), row["subject"], row["layer"], row["structure"])


def merge_cuts(paths: Sequence[Path]) -> Json:
    """One cut file from the same shard of several runs: the first run's reading of a layer under a
    structure by a method stands, and an attempt is listed as skipped only where no run read it."""
    merged = _load(paths[0])

    def read_key(row: Json) -> tuple[str, tuple[str, ...], str]:
        return (row["glyph"], tuple(row["layer"]), row["structure"])

    read = {(*read_key(row), row["method"]["name"]) for row in merged["readings"]}
    skipped = {(row.get("glyph"), row["subject"], tuple(row["layer"]), row["structure"]) for row in merged["skipped"]}
    for path in paths[1:]:
        other = _load(path)
        for row in other["readings"]:
            if (*read_key(row), row["method"]["name"]) not in read:
                read.add((*read_key(row), row["method"]["name"]))
                merged["readings"].append(row)
        for row in other["skipped"]:
            key = (row.get("glyph"), row["subject"], tuple(row["layer"]), row["structure"])
            if key not in skipped:
                skipped.add(key)
                merged["skipped"].append(row)
        for selector, entries in other["drawn"].items():
            merged["drawn"].setdefault(selector, entries)
    done = {read_key(row) for row in merged["readings"]}
    merged["skipped"] = [row for row in merged["skipped"] if ("glyph" not in row or read_key(row) not in done)]
    merged["readings"] = choose(sorted(merged["readings"], key=_key))
    merged["skipped"].sort(key=_key)
    merged["drawn"] = dict(sorted(merged["drawn"].items(), key=lambda item: I.order(item[0])))
    return merged


class Release:
    """One release being built under a folder."""

    def __init__(self, out: Path, version: str):
        if out.exists() and any(out.iterdir()):
            raise ValueError(f"{out} is not empty.")
        self.out, self.version = out, version
        self.counts: dict[str, Json] = {}
        self.forms: dict[str, dict[str, dict[str, Json]]] = {}
        self.library: dict[str, dict[str, dict[str, dict[str, list[str]]]]] = {}
        self.tables: dict[str, list[str]] = {name: [] for name in ("cuts", "skipped")}
        self.drawn: list[tsv.Row] = []
        self.problems: list[str] = []
        self.fonts: set[str] = set()
        self.cuts: set[str] = set()

    def _count(self, font: str) -> Json:
        return self.counts.setdefault(
            font, {"readings": 0, "skipped": 0, "cuts": {}, "structures": set(), "classes": set()}
        )

    def shards(self, runs: Sequence[Path], check: bool = True) -> None:
        """Merge the runs' outline, stroke and cut shards into the release, validating each file,
        and gather what the tables, the indexes and the counts need."""
        for top, kind in (("outlines", "outlines"), ("strokes", "strokes")):
            for name, paths in _shards(runs, top).items():
                content = merge_outlines(paths) if kind == "outlines" else _first(paths)
                self.fonts.add(content["font"])
                if check:
                    self.problems += [f"{name}: {problem}" for problem in problems(kind, content)]
                write(self.out / name, dumps(content))
        for name, paths in _shards(runs, "cuts").items():
            content = merge_cuts(paths)
            font = content["font"]
            if check:
                beside = self.out / "outlines" / font / Path(name).name
                found = problems("cuts", content, _load(beside) if beside.exists() else None)
                self.problems += [f"{name}: {problem}" for problem in found]
            write(self.out / name, dumps(content))
            count = self._count(font)
            count["readings"] += len(content["readings"])
            count["skipped"] += len(content["skipped"])
            self.tables["cuts"] += _lines("cuts", tsv.cut_rows(content))
            self.tables["skipped"] += _lines("skipped", tsv.skipped_rows(content))
            drawn = tsv.drawn_rows(content)
            self.drawn += drawn
            count["structures"] |= {(row["char"], row["structure"]) for row in drawn if row["char"]}
            for row in content["readings"]:
                for cut in row["cuts"]:
                    self.cuts.add(cut["id"])
                    count["cuts"][cut["status"]] = count["cuts"].get(cut["status"], 0) + 1
                    if cut["status"] in ACCEPTED:
                        count["classes"].add(cut["class"])
        for run in runs:
            # A class's form in a style is the first run's that has one, with that run's library.
            mine: set[tuple[str, str, str]] = set()
            for path in sorted((run / "forms").glob("*.json.gz")) if (run / "forms").is_dir() else []:
                content = _load(path)
                for component, styles in content["forms"].items():
                    for style, form in styles.items():
                        held = self.forms.setdefault(content["design"], {}).setdefault(component, {})
                        if style not in held:
                            held[style] = form
                            mine.add((content["design"], component, style))
            for path in sorted((run / "library").glob("*.json.gz")) if (run / "library").is_dir() else []:
                content = _load(path)
                for component, styles in content["library"].items():
                    for style, places in styles.items():
                        if (content["design"], component, style) in mine:
                            self.library.setdefault(content["design"], {}).setdefault(component, {})[style] = places

    def indexes(self) -> None:
        """Write the form and library files, naming no cut that no reading holds."""
        for design, forms in sorted(self.forms.items()):
            self.problems += [
                f"forms/{design}: the form of {component} in {style} names a cut no reading holds."
                for component, styles in sorted(forms.items())
                for style, form in sorted(styles.items())
                if form["cut"] not in self.cuts
            ]
            content = {"format": FORMS, "design": design, "forms": _sorted(forms)}
            self.problems += [f"forms/{design}: {problem}" for problem in problems("forms", content)]
            write(self.out / "forms" / f"{design}.json.gz", dumps(content))
        for design, library in sorted(self.library.items()):
            kept: dict[str, dict[str, dict[str, list[str]]]] = {}
            for component, styles in library.items():
                for style, places in styles.items():
                    # A cut another run's reading took the place of is no longer there to be listed.
                    found = {place: [name for name in names if name in self.cuts] for place, names in places.items()}
                    found = {place: names for place, names in sorted(found.items()) if names}
                    if found:
                        kept.setdefault(component, {})[style] = found
            content = {"format": LIBRARY, "design": design, "library": _sorted(kept)}
            self.problems += [f"library/{design}: {problem}" for problem in problems("library", content)]
            write(self.out / "library" / f"{design}.json.gz", dumps(content))

    def flat(
        self, components: Iterable[Json] = (), classes: Iterable[Json] = (), verdicts: Iterable[Json] = ()
    ) -> None:
        """Write the flat tables: the cuts, drawn IDS, structures and skipped attempts of every
        font, and the component, class and verdict rows given."""
        for name, lines in self.tables.items():
            write(self.out / f"{name}.tsv.gz", tsv.write_table(name, [], self.version) + "".join(lines))
        write(self.out / "drawn.tsv.gz", tsv.write_table("drawn", self.drawn, self.version))
        write(
            self.out / "structures.tsv.gz", tsv.write_table("structures", tsv.structure_rows(self.drawn), self.version)
        )
        for name, rows in (("components", components), ("classes", classes), ("verdicts", verdicts)):
            write(self.out / f"{name}.tsv", tsv.write_table(name, list(rows), self.version))

    def summary(self) -> Json:
        """Counts per font, sets as their sizes."""
        return {
            font: {
                **count,
                "structures": len(count["structures"]),
                "classes": len(count["classes"]),
                "cuts": dict(sorted(count["cuts"].items())),
            }
            for font, count in sorted(self.counts.items())
        }

    def finish(self, commit: str | None = None) -> Json:
        """Write the registry, the licence texts, the README, the manifest and the checksums."""
        fonts = sorted({*self.fonts, *self.counts})
        write(self.out / "fonts.json", dumps(pins.fonts()))
        texts = resource("LICENSES")
        known = {row["id"]: row for row in pins.fonts()["fonts"]}
        rows = [known[font] for font in fonts if font in known]
        for name in sorted({"CC0-1.0.txt", *(row["licenceFile"] for row in rows if "licenceFile" in row)}):
            shutil.copyfile(texts / name, _ensure(self.out / "LICENSES" / name))
        write(self.out / "README.md", readme(self.version, self.summary(), self.forms, fonts))
        files = []
        for path in sorted(self.out.rglob("*")):
            if path.is_file() and path.name not in ("manifest.json", "SHA256SUMS"):
                files.append(
                    {
                        "path": path.relative_to(self.out).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": _digest(path),
                    }
                )
        manifest: Json = {
            "format": MANIFEST,
            "release": self.version,
            "tool": {"name": "han-decompose", "version": __version__, **({"commit": commit} if commit else {})},
            "fonts": [{"id": row["id"], "sha256": row["sha256"]} for row in pins.fonts()["fonts"]],
            "counts": self.summary(),
            "files": files,
        }
        self.problems += [f"manifest.json: {problem}" for problem in problems("manifest", manifest)]
        write(self.out / "manifest.json", dumps(manifest))
        sums = [f"{row['sha256']}  {row['path']}\n" for row in files]
        sums.append(f"{_digest(self.out / 'manifest.json')}  manifest.json\n")
        write(self.out / "SHA256SUMS", "".join(sums))
        return manifest


def _first(paths: Sequence[Path]) -> Json:
    """The first run's file of a shard that several runs may hold."""
    return _load(paths[0])


def _sorted(nested: dict[str, Any]) -> dict[str, Any]:
    """A nested mapping with every level in key order."""
    return {key: _sorted(value) if isinstance(value, dict) else value for key, value in sorted(nested.items())}


def _ensure(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _digest(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _lines(name: str, rows: Sequence[tsv.Row]) -> list[str]:
    """Rows as the lines of a table, without its two heading lines."""
    return tsv.write_table(name, rows).split("\n", 2)[2].splitlines(keepends=True) if rows else []


def readme(version: str, counts: Json, forms: Json, fonts: Sequence[str]) -> str:
    """The release's README: what it holds, how much, and every font with its licence and
    copyright line."""
    known = {row["id"]: row for row in pins.fonts()["fonts"]}
    lines = [
        f"# han-decompose data {version}",
        "",
        "Which contours of a font's Han glyph belong to which component of its ideographic description",
        "sequence. Every part is a set of contours the font already draws.",
        "",
        "The files are laid out and defined by <https://github.com/mkpoli/han-decompose/blob/main/docs/format.md>.",
        "",
        "## What is here",
        "",
        "| Font | Glyphs read | Cuts accepted | Cuts refused | Classes cut | Structures | Attempts skipped |",
        "|---|---|---|---|---|---|---|",
    ]
    for font, count in counts.items():
        lines.append(
            f"| `{font}` | {count['readings']:,} | {count['cuts'].get('accepted', 0):,} | "
            f"{count['cuts'].get('refused', 0):,} | {count['classes']:,} | {count['structures']:,} | "
            f"{count['skipped']:,} |"
        )
    if forms:
        lines += ["", "| Design | Classes with a chosen form |", "|---|---|"]
        lines += [f"| `{design}` | {len(held):,} |" for design, held in sorted(forms.items())]
    statuses: dict[str, int] = {}
    for count in counts.values():
        for status, number in count["cuts"].items():
            statuses[status] = statuses.get(status, 0) + number
    judged = statuses.get("reviewed-right", 0) + statuses.get("reviewed-wrong", 0)
    lines += [
        "",
        "By status, over all fonts: " + ", ".join(f"{n:,} {s}" for s, n in sorted(statuses.items())) + "."
        if statuses
        else "",
        "",
        "A cut says how it was made and checked. A `refused` cut failed a check and is kept so that it can be",
        "reviewed. `calibrated` names the component whose reviewed cuts set the limits of the checks, or is",
        "`false`: the limits are then borrowed from another component or font.",
        f"A person has judged {judged:,} of the cuts in this release (`reviewed-right`, `reviewed-wrong`)."
        if judged
        else "No cut in this release has been judged by a person.",
        "",
        "## Licences",
        "",
        "An outline file and a stroke file are under the licence of its font, named below. Every other file",
        "is label data under CC0-1.0. The texts are in `LICENSES/`. This is how the project applies the terms",
        "and no legal advice: <https://github.com/mkpoli/han-decompose/blob/main/docs/licensing.md>.",
        "",
        "### Fonts",
        "",
    ]
    for font in fonts:
        row = known.get(font)
        if row:
            lines.append(
                f"- `{font}`: {row['name']} {row['version']}, {row['licence']}. {row['copyright']} <{row['url']}>"
            )
    lines += [
        "",
        "## Checking a download",
        "",
        "`SHA256SUMS` lists every file; `manifest.json` adds the pinned fonts and the counts above.",
        "",
    ]
    return "\n".join(lines)


def pack(release: Path, dist: Path) -> list[Path]:
    """The release as the files of a release page: one archive of outlines, one of strokes and one
    of cuts per font, and the tables, indexes and registries as they are. Archives are written
    with fixed times and owners, so the same release packs to the same bytes."""
    if dist.exists() and any(dist.iterdir()):
        raise ValueError(f"{dist} is not empty.")
    dist.mkdir(parents=True, exist_ok=True)
    made = []
    groups: dict[str, list[Path]] = {}
    for path in sorted(release.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(release).parts
        if parts[0] in ("outlines", "strokes", "cuts"):
            groups.setdefault(f"{parts[0]}.{parts[1].replace('@', '-')}", []).append(path)
        elif parts[0] in ("LICENSES", "library", "forms"):
            groups.setdefault(parts[0].lower(), []).append(path)
        else:
            shutil.copyfile(path, dist / path.name)
            made.append(dist / path.name)
    for name, paths in sorted(groups.items()):
        target = dist / f"{name}.tar.gz"
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in paths:
                info = tarfile.TarInfo(path.relative_to(release).as_posix())
                info.size, info.mtime, info.mode = path.stat().st_size, 0, 0o644
                with path.open("rb") as file:
                    archive.addfile(info, file)
        target.write_bytes(gzip.compress(raw.getvalue(), 6, mtime=0))
        made.append(target)
    sums = "".join(f"{_digest(path)}  {path.name}\n" for path in sorted(made) if path.name != "SHA256SUMS")
    (dist / "SHA256SUMS.assets").write_text(sums, encoding="utf-8")
    return [*made, dist / "SHA256SUMS.assets"]
