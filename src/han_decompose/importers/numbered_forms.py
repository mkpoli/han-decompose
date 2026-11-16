"""The numbered components han-compose cut for its Sans style, taken over as cuts of their hosts.

han-compose's `data/numbered-forms.json` holds an outline per numbered component and style. A Sans
outline was cut from a host character's glyph with han-compose's own cutter, but the file names
neither the host nor the contours. Both are found again here: among the characters BabelStone
describes with the component, the first whose glyph draws every contour of the stored outline, at
the same position, is the host, and those contours are the cut. An outline that is no set of whole
contours of any host (han-compose can cut inside a contour) is left out, as is one the file marks
as the PUA glyph standing in.
"""

import gzip
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pathops

from .. import geometry as G
from .. import identifiers as I
from .. import pins
from ..cutters import lift, reading
from ..descriptions import Table
from ..ids import leaves, walk
from ..outline import Contour
from ..pieces import Drawing, Glyph
from ..schema import Json

SOURCE = "han-compose-numbered-forms"
REGISTRY = "ids-input-components"
#: The style of the file whose forms are cuts of host glyphs, and the chain it was cut from.
STYLE = "sans"
#: The designs of the fonts the file was cut from, in order.
DESIGNS = ("source-han-sans", "plangothic")


def match(form: Sequence[Sequence[object]], contours: Sequence[Contour]) -> list[int] | None:
    """The contours of a glyph that a stored outline consists of, or None unless every contour of
    the outline is one of the glyph's: the same pen commands and the same points, to a hundredth
    of a unit."""
    found = []
    for commands, points in form:
        wanted = [round(float(value) * 100) for value in points]  # type: ignore[attr-defined]
        index = next(
            (
                at
                for at, (letters, held) in enumerate(contours)
                if at not in found
                and letters == commands
                and len(held) == len(wanted)
                and all(abs(a - b) <= 1 for a, b in zip(held, wanted, strict=True))
            ),
            None,
        )
        if index is None:
            return None
        found.append(index)
    return sorted(found)


def forms(file: Json, table: Table) -> dict[str, list[list[object]]]:
    """The Sans outlines that are cuts, by the component's text: every contour of every group, the
    PUA fallbacks left out."""
    names = {row.pua: name for name, row in table.numbered.items() if row.pua}
    fallback = {f"&bsp:{number};" for number in file["fallback"]}
    out = {}
    for pua, groups in file["forms"][STYLE].items():
        name = names.get(pua)
        if name is not None and name not in fallback:
            out[name] = [contour for group in groups for contour in group]
    return out


def host_of(
    form: Sequence[Sequence[object]], hosts: str, drawings: Sequence[Drawing]
) -> tuple[Glyph, list[int]] | None:
    """The first host, in the first font of the chain, whose glyph draws the whole outline."""
    for host in hosts:
        for drawing in drawings:
            glyph = drawing.glyph(f"U+{ord(host):04X}")
            if glyph is None:
                continue
            contours = match(form, glyph.contours)
            if contours is not None:
                return glyph, contours
    return None


def imports(
    file: Json,
    table: Table,
    registry: Sequence[Json],
    drawings: Sequence[Drawing],
    references: dict[str, tuple[str, G.Array | None]],
) -> Iterator[lift.Outcome]:
    """Each Sans form that is whole contours of a host glyph, as a reading of the host under the
    BabelStone description that names the component, and as the component's chosen form."""
    used = {f"&bsp:{row['text'][1:-1]};": row["usedIn"] for row in registry if row["kind"] == "numbered"}
    cutter = file["sources"]["cutter"].split()
    for name, form in sorted(forms(file, table).items(), key=lambda item: int(item[0][5:-1])):
        found = host_of(form, used.get(name, ""), drawings)
        if found is None:
            continue
        glyph, contours = found
        host = chr(int(glyph.selector[2:], 16))
        for description in table.of(host):
            try:
                root = description.tree()
            except ValueError:
                continue
            if [leaf.text for leaf in leaves(root)].count(name) != 1:
                continue
            path, node = next((path, node) for path, node in walk(root) if node.leaf and node.text == name)
            evidence: Json = {"importedFrom": SOURCE}
            glyph_id, print_ = references.get(name, (None, None))
            if print_ is not None:
                ink = pathops.Path()
                for index in contours:
                    glyph.paths[index].draw(ink.getPen())
                ink.simplify()
                evidence["reference"] = reading.number(lift.like(lift.print_of(lift.mask(ink)), print_), 4)
                evidence["referenceGlyph"] = glyph_id
            cut = reading.cut(glyph, description, root, path, node, contours, "accepted", "axis", evidence=evidence)
            (row,) = reading.reading(glyph, description, root, "axis", "contour", [cut])
            row["method"] = {"name": "axis", "tool": cutter[0], "commit": cutter[-1], "grain": "contour"}
            out = lift.Outcome(I.component_of(name), "numbered", readings=[row])
            out.form = {"cut": cut["id"], "sig": cut["sig"], "basis": "imported"}
            out.library = {cut["place"]: [cut["id"]]}
            out.glyphs[row["glyph"]] = glyph.record()
            yield out
            break


def pinned(cache: Path | None = None) -> tuple[Json, list[Json]]:
    """The pinned file of han-compose, and the pinned component registry's rows."""
    paths = pins.source_paths(pins.source(SOURCE), cache, fetch=False)
    file: Json = json.loads(paths["numbered-forms.json"].read_text(encoding="utf-8"))
    registry = pins.source_paths(pins.source(REGISTRY), cache, fetch=False)
    rows: list[Json] = json.loads(gzip.decompress(registry["custom-components.json.gz"].read_bytes()))["components"]
    return file, rows
