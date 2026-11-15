"""Build a data release: the shards of several cutting runs merged into the one layout
`docs/format.md` gives, with the flat tables, the registries, a README that names every source
and licence, the licence texts, a manifest and checksums; then packed as one archive per font and
source for the release page.

A run's folder holds `outlines/` and `cuts/` shards, and may hold `forms/` and `library/`. Runs
are given in order of precedence: where two hold a reading of the same glyph under the same
description, the earlier run's stands.
"""

import gzip
import hashlib
import io
import json
import shutil
import tarfile
from collections.abc import Iterable, Sequence
from pathlib import Path

from . import __version__, pins, tsv
from . import identifiers as I
from .resources import resource
from .schema import Json, problems
from .store import FORMS, LIBRARY, dumps, write

MANIFEST = "han-decompose/manifest@1.0"
ACCEPTED = ("accepted", "reviewed-right")


def _load(path: Path) -> Json:
    value: Json = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())
    return value


def _shards(runs: Sequence[Path], top: str) -> dict[str, list[Path]]:
    """Every shard under `top` of every run, by its path in the release, runs in order."""
    out: dict[str, list[Path]] = {}
    for run in runs:
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
    merged["glyphs"] = dict(sorted(merged["glyphs"].items(), key=lambda item: _order(item[0])))
    return merged


def _order(selector: str) -> tuple[int, int, int]:
    match = I.SELECTOR.fullmatch(selector)
    assert match is not None
    if match["gid"] is not None:
        return (1, int(match["gid"]), 0)
    return (0, int(match["base"], 16), int(match["selector"], 16) if match["selector"] else 0)


def _key(row: Json) -> tuple[tuple[int, int, int], str, str]:
    selector = I.split_glyph_id(row["glyph"])[1] if "glyph" in row else "gid.0"
    return (_order(selector), row["subject"], row["description"])


def merge_cuts(paths: Sequence[Path]) -> Json:
    """One cut file from the same shard of several runs: the first run's reading of a glyph under
    a description stands, and an attempt is listed as skipped only where no run read it."""
    merged = _load(paths[0])
    read = {(row["glyph"], row["description"]) for row in merged["readings"]}
    skipped = {(row.get("glyph"), row["subject"], row["description"]) for row in merged["skipped"]}
    for path in paths[1:]:
        other = _load(path)
        if other["terms"].get("guide") and not merged["terms"].get("guide"):
            merged["terms"]["guide"] = other["terms"]["guide"]
            merged["terms"]["notices"] = sorted({*merged["terms"]["notices"], *other["terms"]["notices"]})
        for row in other["readings"]:
            if (row["glyph"], row["description"]) not in read:
                read.add((row["glyph"], row["description"]))
                merged["readings"].append(row)
        for row in other["skipped"]:
            key = (row.get("glyph"), row["subject"], row["description"])
            if key not in skipped:
                skipped.add(key)
                merged["skipped"].append(row)
    merged["skipped"] = [row for row in merged["skipped"] if (row.get("glyph"), row["description"]) not in read]
    merged["readings"].sort(key=_key)
    merged["skipped"].sort(key=_key)
    return merged


def _score(cut: Json) -> float:
    evidence = cut.get("evidence", {})
    return float(evidence.get("fit", evidence.get("match", 0)))


class Release:
    """One release being built under a folder."""

    def __init__(self, out: Path, version: str):
        if out.exists() and any(out.iterdir()):
            raise ValueError(f"{out} is not empty.")
        self.out, self.version = out, version
        self.counts: dict[str, dict[str, Json]] = {}
        self.library: dict[str, dict[str, dict[str, list[tuple[float, str]]]]] = {}
        self.forms: dict[str, dict[str, Json]] = {}
        self.lifted: dict[str, dict[str, dict[str, list[str]]]] = {}
        self.tables: dict[tuple[str, str], list[str]] = {}
        self.problems: list[str] = []
        self.guides: set[str] = set()
        self.fonts: set[str] = set()
        self.chains = {font: name for name, fonts in pins.fonts()["chains"].items() for font in fonts}

    def _count(self, font: str, source: str) -> Json:
        return self.counts.setdefault(font, {}).setdefault(
            source, {"readings": 0, "skipped": 0, "cuts": {}, "components": set()}
        )

    def shards(self, runs: Sequence[Path], check: bool = True) -> None:
        """Merge the runs' outline and cut shards into the release, validating each file, and
        gather what the tables, the indexes and the counts need."""
        outlines = _shards(runs, "outlines")
        for name, paths in outlines.items():
            content = merge_outlines(paths)
            self.fonts.add(content["font"])
            if check:
                self.problems += [f"{name}: {problem}" for problem in problems("outlines", content)]
            write(self.out / name, dumps(content))
        for name, paths in _shards(runs, "cuts").items():
            content = merge_cuts(paths)
            font, source = content["font"], content["source"]
            self.guides |= {row["method"]["guide"] for row in content["readings"] if "guide" in row["method"]}
            if check:
                beside = self.out / "outlines" / font / Path(name).name
                found = problems("cuts", content, _load(beside) if beside.exists() else None)
                self.problems += [f"{name}: {problem}" for problem in found]
            write(self.out / name, dumps(content))
            count = self._count(font, source)
            count["readings"] += len(content["readings"])
            count["skipped"] += len(content["skipped"])
            self.tables.setdefault(("cuts", source), []).extend(_lines("cuts", tsv.cut_rows(content)))
            self.tables.setdefault(("skipped", source), []).extend(_lines("skipped", tsv.skipped_rows(content)))
            chain = self.chains.get(font)
            for row in content["readings"]:
                for cut in row["cuts"]:
                    count["cuts"][cut["status"]] = count["cuts"].get(cut["status"], 0) + 1
                    if cut["status"] in ACCEPTED:
                        count["components"].add(cut["component"])
                        if chain and cut["path"]:
                            places = self.library.setdefault(chain, {}).setdefault(cut["component"], {})
                            places.setdefault(cut["place"], []).append((-_score(cut), cut["id"]))
        for run in runs:
            for kind, held in (("forms", self.forms), ("library", self.lifted)):
                for path in sorted((run / kind).glob("*.json.gz")) if (run / kind).is_dir() else []:
                    content = _load(path)
                    for component, value in content[kind].items():
                        held.setdefault(content["chain"], {}).setdefault(component, value)

    def indexes(self) -> None:
        """Write the form and library files: a lifted component keeps the library that confirms
        its form; every other component lists its accepted cuts by place, best first."""
        for chain, forms in sorted(self.forms.items()):
            content = {"format": FORMS, "chain": chain, "forms": dict(sorted(forms.items()))}
            self.problems += [f"forms/{chain}: {problem}" for problem in problems("forms", content)]
            write(self.out / "forms" / f"{chain}.json.gz", dumps(content))
        for chain in sorted({*self.library, *self.lifted}):
            library: dict[str, dict[str, list[str]]] = {}
            for component, places in self.library.get(chain, {}).items():
                library[component] = {
                    place: [name for _, name in sorted(cuts)] for place, cuts in sorted(places.items())
                }
            library.update(self.lifted.get(chain, {}))
            content = {"format": LIBRARY, "chain": chain, "library": dict(sorted(library.items()))}
            write(self.out / "library" / f"{chain}.json.gz", dumps(content))

    def flat(self, components: Iterable[Json]) -> None:
        """Write the flat tables, one per source."""
        for (name, source), lines in sorted(self.tables.items()):
            head = tsv.write_table(name, [], self.version)
            write(self.out / f"{name}.{source}.tsv.gz", head + "".join(lines))
        by: dict[str, list[Json]] = {}
        for row in components:
            by.setdefault(row["source"], []).append(row)
        for source, rows in sorted(by.items()):
            write(self.out / f"components.{source}.tsv", tsv.write_table("components", rows, self.version))
        write(self.out / "verdicts.tsv", tsv.write_table("verdicts", [], self.version))

    def summary(self) -> Json:
        """Counts per font and source, sets as their sizes."""
        return {
            font: {
                source: {**count, "components": len(count["components"]), "cuts": dict(sorted(count["cuts"].items()))}
                for source, count in sorted(sources.items())
            }
            for font, sources in sorted(self.counts.items())
        }

    def finish(self, commit: str | None = None) -> Json:
        """Write the registries, the licence texts, the README, the manifest and the checksums."""
        fonts = sorted({*self.fonts, *self.counts})
        sources = sorted({source for held in self.counts.values() for source in held})
        write(self.out / "fonts.json", dumps(pins.fonts()))
        write(self.out / "sources.json", dumps(pins.sources()))
        texts = resource("LICENSES")
        known = {row["id"]: row for row in pins.fonts()["fonts"]}
        rows = [known[font] for font in fonts if font in known]
        rows += [row for row in pins.sources()["sources"] if row["role"] != "guide" or row["id"] in self.guides]
        for name in sorted({row["licenceFile"] for row in rows if "licenceFile" in row}):
            shutil.copyfile(texts / name, _ensure(self.out / "LICENSES" / name))
        text = readme(self.version, self.summary(), self.forms, fonts, sources, sorted(self.guides))
        write(self.out / "README.md", text)
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
            "sources": [
                {"id": row["id"], "pin": row["pin"], "files": {f["file"]: f["sha256"] for f in row.get("files", ())}}
                for row in pins.sources()["sources"]
            ],
            "counts": self.summary(),
            "files": files,
        }
        write(self.out / "manifest.json", dumps(manifest))
        sums = [f"{row['sha256']}  {row['path']}\n" for row in files]
        sums.append(f"{_digest(self.out / 'manifest.json')}  manifest.json\n")
        write(self.out / "SHA256SUMS", "".join(sums))
        return manifest


def _ensure(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _digest(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _lines(name: str, rows: Sequence[tsv.Row]) -> list[str]:
    """Rows as the lines of a table, without its two heading lines."""
    return tsv.write_table(name, rows).split("\n", 2)[2].splitlines(keepends=True) if rows else []


def readme(
    version: str, counts: Json, forms: Json, fonts: Sequence[str], sources: Sequence[str], guides: Sequence[str]
) -> str:
    """The release's README: what it holds, how much, and every font and source with its licence
    and attribution."""
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
        "| Font | Descriptions | Glyphs read | Cuts accepted | Cuts refused | Components cut | Attempts skipped |",
        "|---|---|---|---|---|---|---|",
    ]
    for font, held in counts.items():
        for source, count in held.items():
            lines.append(
                f"| `{font}` | `{source}` | {count['readings']:,} | {count['cuts'].get('accepted', 0):,} | "
                f"{count['cuts'].get('refused', 0):,} | {count['components']:,} | {count['skipped']:,} |"
            )
    if forms:
        lines += ["", "| Chain | Components with a chosen form |", "|---|---|"]
        lines += [f"| `{chain}` | {len(held):,} |" for chain, held in sorted(forms.items())]
    lines += [
        "",
        "A cut says how it was made and checked. `status` is `accepted` or `refused`; a refused cut failed a",
        "check and is kept so that it can be reviewed. `calibrated` names the component whose reviewed cuts",
        "set the limits of the checks, or is `false`: the limits were set on 山 in Noto Sans CJK JP and",
        "Plangothic and are borrowed for every other component and font. No cut in this release has been",
        "judged by a person.",
        "",
        "## Licences",
        "",
        "An outline file is under the licence of its font. A cut file holds contour indices and labels, is",
        "under the licence of its font, and states the terms of the description source its labels were read",
        "from; a flat table holds the rows of one source. The texts are in `LICENSES/`. This is how the",
        "project applies the terms and no legal advice:",
        "<https://github.com/mkpoli/han-decompose/blob/main/docs/licensing.md>.",
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
    lines += ["", "### Sources", ""]
    for row in pins.sources()["sources"]:
        if row["role"] == "guide" and row["id"] not in guides:
            continue
        role = "descriptions" if row["id"] in sources else row["role"]
        lines.append(f"- `{row['id']}` ({role}): {row['attribution']}. {row['licence']}. Pin: {row['pin']}.")
    lines += [
        "",
        "Cuts made along a guide name it and its licence, and their files carry its attribution."
        if guides
        else "No cut in this release was made along a guide.",
        "",
        "## Checking a download",
        "",
        "`SHA256SUMS` lists every file; `manifest.json` adds the pinned inputs and the counts above.",
        "",
    ]
    return "\n".join(lines)


def pack(release: Path, dist: Path) -> list[Path]:
    """The release as the files of a release page: one archive of outlines per font, one of cuts
    per font and source, and the tables, indexes and registries as they are. Archives are written
    with fixed times and owners, so the same release packs to the same bytes."""
    dist.mkdir(parents=True, exist_ok=True)
    made = []
    groups: dict[str, list[Path]] = {}
    for path in sorted(release.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(release).parts
        if parts[0] == "outlines":
            groups.setdefault(f"outlines.{parts[1].replace('@', '-')}", []).append(path)
        elif parts[0] == "cuts":
            groups.setdefault(f"cuts.{parts[1].replace('@', '-')}.{parts[2]}", []).append(path)
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
