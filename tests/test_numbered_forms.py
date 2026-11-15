import gzip
import json
from pathlib import Path

import pytest

from han_decompose import descriptions, numbered, pins, release
from han_decompose import identifiers as I
from han_decompose.cutters import lift
from han_decompose.importers import numbered_forms
from han_decompose.pieces import Drawing
from han_decompose.schema import problems
from han_decompose.store import Store, dumps, write

from .fonts import pinned_chain, pinned_face

SQUARE = ("MLLL", [0, 0, 0, 10000, 10000, 10000, 10000, 0])
BAR = ("MLLL", [20000, 0, 20000, 5000, 30000, 5000, 30000, 0])


def test_an_outline_is_found_among_a_glyphs_contours() -> None:
    contours = [SQUARE, BAR, SQUARE]
    assert numbered_forms.match([["MLLL", [200, 0, 200, 50, 300, 50, 300, 0]]], contours) == [1]
    assert numbered_forms.match([["MLLL", [0, 0, 0, 100, 100, 100, 100, 0]]] * 2, contours) == [0, 2]
    assert numbered_forms.match([["MLLL", [0, 0, 0, 100, 100, 100, 100, 0]]] * 3, contours) is None
    assert numbered_forms.match([["MLLL", [200.004, 0, 200, 50, 300, 50.006, 300, 0]]], contours) == [1]
    assert numbered_forms.match([["MLLL", [201, 0, 201, 50, 301, 50, 301, 0]]], contours) is None
    assert numbered_forms.match([["MLLQ2", [200, 0, 200, 50, 300, 50, 300, 0]]], contours) is None


def pinned() -> tuple[dict[str, object], list[dict[str, object]], descriptions.Table, list[Drawing]]:
    try:
        file, registry = numbered_forms.pinned()
        table = descriptions.table("babelstone")
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    return file, registry, table, [Drawing(face) for face in pinned_chain("sans").faces]


def test_the_forms_that_are_whole_contours_of_a_host_are_taken_over(tmp_path: Path) -> None:
    file, registry, table, drawings = pinned()
    references = lift.numbered(table, Drawing(pinned_face(numbered.FONT)))
    assert len(numbered_forms.forms(file, table)) == 60
    found = list(numbered_forms.imports(file, table, registry, drawings, references))
    assert len(found) == 22 and len({outcome.component for outcome in found}) == 22
    store = Store()
    for outcome in found:
        (row,) = outcome.readings
        (cut,) = row["cuts"]
        assert row["method"] == {"name": "axis", "tool": "han-compose", "commit": "bf13d98", "grain": "contour"}
        assert outcome.form == {"cut": cut["id"], "sig": cut["sig"], "basis": "imported"}
        assert cut["component"] == outcome.component and outcome.library == {cut["place"]: [cut["id"]]}
        assert cut["evidence"]["referenceGlyph"].startswith("babelstone-han-pua@1.472/U+")
        for glyph, record in outcome.glyphs.items():
            store.record(*I.split_glyph_id(glyph), record)
        store.reading(row)
        store.form("sans", outcome.component, outcome.form, outcome.library)
    files = dict(store.files())
    for name, content in files.items():
        kind = name.split("/")[0]
        outlines = files.get(f"outlines/{name.split('/')[1]}/{name.split('/')[-1]}") if kind == "cuts" else None
        assert problems(kind, content, outlines) == [], name
    store.write(tmp_path / "import")
    # In a release the imported form stands, and a library lists only cuts the release holds.
    other = tmp_path / "lift"
    gone = "noto-sans-cjk-jp@2.004/U+4E00~babelstone.00000000~0"
    first = found[0]
    assert first.form is not None
    place = next(iter(first.library))
    forms = {first.component: {"cut": gone, "sig": "00000000", "basis": "reference"}}
    write(
        other / "forms" / "sans.json.gz", dumps({"format": "han-decompose/forms@1.0", "chain": "sans", "forms": forms})
    )
    library = {first.component: {place: [gone], "B": [gone]}}
    write(
        other / "library" / "sans.json.gz",
        dumps({"format": "han-decompose/library@1.0", "chain": "sans", "library": library}),
    )
    built = release.Release(tmp_path / "out", "v0.0.1")
    built.shards([tmp_path / "import", other])
    built.indexes()
    assert built.problems == []
    out = tmp_path / "out"
    assert (
        json.loads(gzip.decompress((out / "forms" / "sans.json.gz").read_bytes()))["forms"][first.component]
        == first.form
    )
    listed = json.loads(gzip.decompress((out / "library" / "sans.json.gz").read_bytes()))["library"][first.component]
    assert listed == {place: [first.form["cut"]]}
