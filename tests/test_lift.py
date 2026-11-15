import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from han_decompose import descriptions, pins
from han_decompose import geometry as G
from han_decompose import identifiers as I
from han_decompose.cutters import lift
from han_decompose.cutters.deal import Skipped
from han_decompose.descriptions import Table
from han_decompose.pieces import Drawing
from han_decompose.schema import problems
from han_decompose.store import Store

from .fonts import pinned_chain

FIXTURES = Path(__file__).parent / "fixtures" / "lift"


def table() -> Table:
    out = Table("chise")
    for char, text in {"冐": "⿱&X;⺜", "肖": "⿱⺌&X;", "胃": "⿱田&X;", "育": "⿱𠫓&X;", "骨": "⿱冎⿵&X;一"}.items():
        out.add(char, text)
    out.add("育", "⿱&X;&X;", "apparent")
    out.add("謂", "⿰言⿱田&X;")
    out.add("亂", "⿰&Y;乚")
    return out


def test_the_hosts_of_a_component_and_what_to_lift_from_each() -> None:
    row = {"text": "&X;", "kind": "entity", "usedIn": "冐肖胃育骨謂亂", "subtraction": "㇯㇯媿鬼女"}
    found = lift.recipes(row, table())
    assert [(r.host, r.parts, r.op, r.side) for r in found] == [
        ("媿", ["女", "鬼"], "㇯", 0),
        ("冐", ["⺜"], "⿱", 0),
        ("肖", ["⺌"], "⿱", 1),
        ("胃", ["田"], "⿱", 1),
        ("育", ["𠫓"], "⿱", 1),
        ("骨", ["冎", "一"], None, 0),
        ("謂", ["言", "田"], None, 0),
    ]
    assert found[0].description == descriptions.Description("ids-input-components", "&X;", "㇯㇯媿鬼女")
    assert found[-1].siblings == ["言", "田"] and found[1].siblings == ["⺜"]
    assert lift.recipes({"text": "&Z;", "kind": "entity", "usedIn": "亂"}, table()) == []


def test_a_print_reads_the_shape_whatever_its_size() -> None:
    small, large = np.zeros((126, 126), dtype=bool), np.zeros((126, 126), dtype=bool)
    small[10:20, 10:30] = True
    large[40:100, 5:125] = True
    assert lift.like(lift.print_of(small), lift.print_of(large)) == 1.0
    assert lift.print_of(np.zeros((126, 126), dtype=bool)) is None and lift.like(None, lift.print_of(small)) == 0.0


def test_a_part_sits_where_its_operator_puts_it() -> None:
    upper, lower = np.zeros((126, 126), dtype=bool), np.zeros((126, 126), dtype=bool)
    upper[5:40, 20:100] = True
    lower[60:120, 20:100] = True
    (recipe,) = lift.recipes({"text": "&X;", "kind": "entity", "usedIn": "冐"}, table())
    assert lift.placed(recipe, lower, upper) and not lift.placed(recipe, upper, lower)
    (other,) = lift.recipes({"text": "&X;", "kind": "entity", "usedIn": "肖"}, table())
    assert lift.placed(other, upper, lower) and not lift.placed(other, lower, upper)


def pinned(chain: str) -> tuple[dict[str, Table], list[Drawing], dict[str, tuple[str, G.Array | None]]]:
    try:
        tables = {source: descriptions.table(source) for source in ("chise", "zi-tools")}
        paths = pins.source_paths(pins.source("glyphwiki"), fetch=False)
    except pins.PinError:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    references = lift.glyphwiki(json.loads(gzip.decompress(paths["custom-outlines.json.gz"].read_bytes())))
    return tables, [Drawing(face) for face in pinned_chain(chain).faces], references


def test_a_component_is_what_a_host_leaves_and_its_form_is_the_cut_that_stands() -> None:
    tables, drawings, references = pinned("sans")
    row = next(row for row in lift.registry() if row["text"] == "&CDP-8958;")
    outcome = lift.component(row, tables, drawings, references)
    assert outcome.component == "chise:CDP-8958" and outcome.form is not None
    assert outcome.form["basis"] == "reference" and outcome.form["hosts"] == len(outcome.readings)
    chosen = next(row for row in outcome.readings if any(cut["id"] == outcome.form["cut"] for cut in row["cuts"]))
    cut = next(cut for cut in chosen["cuts"] if cut["id"] == outcome.form["cut"])
    assert cut["status"] == "accepted" and cut["checks"]["reference"]["pass"] and cut["calibrated"] is False
    assert cut["evidence"]["referenceGlyph"] == "cdp-8958" and chosen["method"]["name"] == "lift"
    assert all(
        member in {c["id"] for r in outcome.readings for c in r["cuts"]}
        for ids in outcome.library.values()
        for member in ids
    )
    store = Store()
    for glyph, record in outcome.glyphs.items():
        store.record(*I.split_glyph_id(glyph), record)
    for found in outcome.readings:
        store.reading(found)
    for skipped, font in outcome.skipped:
        store.skip(skipped, font)
    store.form("sans", outcome.component, outcome.form, outcome.library)
    files = dict(store.files())
    for name, content in files.items():
        kind = name.split("/")[0]
        outlines = files.get(f"outlines/{name.split('/')[1]}/{name.split('/')[-1]}") if kind == "cuts" else None
        assert problems(kind, content, outlines) == [], name
    assert "forms/sans.json.gz" in files and "library/sans.json.gz" in files


def test_a_subtraction_is_read_as_a_cut_of_the_component_itself() -> None:
    tables, drawings, references = pinned("sans")
    row = next(row for row in lift.registry() if row["text"] == "&CDP-8958;")
    recipe = lift.recipes(row, tables["chise"])[0]
    assert (recipe.host, recipe.parts, recipe.op) == ("冐", ["⺜"], "㇯")
    try:
        got = lift.lift(drawings, recipe)
    except Skipped as reason:
        row_, font = lift.skipped(recipe, drawings, reason)
        assert row_["subject"] == "chise:CDP-8958" and font == drawings[0].id
        return
    found = lift.record(got, "&CDP-8958;")
    assert found["subject"] == "chise:CDP-8958" and found["description"].startswith("ids-input-components.")
    (cut,) = found["cuts"]
    assert cut["path"] == [] and cut["place"] == "" and cut["component"] == "ids:㇯冐⺜" and not found["complete"]


def reference() -> dict[str, dict[str, tuple[str, float, float, int, float | None, str]]]:
    out: dict[str, dict[str, tuple[str, float, float, int, float | None, str]]] = {"sans": {}, "serif": {}}
    text = gzip.decompress((FIXTURES / "custom-forms.tsv.gz").read_bytes()).decode("utf-8")
    for line in text.splitlines()[1:]:
        chain, component, host, _, match, margin, agree, likeness, library = line.split("\t")
        scores = (float(match), float(margin), int(agree), float(likeness) if likeness else None)
        out[chain][I.component_of(component)] = (host, *scores, library)
    return out


@pytest.mark.reproduction
@pytest.mark.parametrize("chain", ["sans", "serif"])
def test_the_forms_ids_input_cut_for_han_compose_reproduce(chain: str) -> None:
    """Every component has the form ids-input gave it: the same host, the same scores and the same
    number of library cuts in each place. `expected.json` names the components that differ."""
    pinned(chain)
    wanted = reference()[chain]
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))[chain]
    mine = {}
    kinds: dict[str, int] = {}
    for outcome in lift.run(chain):
        if outcome.form is None:
            continue
        kinds[outcome.kind] = kinds.get(outcome.kind, 0) + 1
        cut = next(cut for row in outcome.readings for cut in row["cuts"] if cut["id"] == outcome.form["cut"])
        host = chr(int(cut["id"].split("~")[0].split("/U+")[1], 16))
        evidence = cut["evidence"]
        library = " ".join(f"{place}:{len(cuts)}" for place, cuts in sorted(outcome.library.items()))
        scores = (evidence["match"], evidence["margin"], evidence["agree"], evidence.get("reference"))
        mine[outcome.component] = (host, *scores, library)
    assert sorted(set(wanted) - set(mine)) == expected["lost"]
    assert sorted(set(mine) - set(wanted)) == expected["gained"]
    differ = []
    for component in sorted(set(mine) & set(wanted)):
        found, other = mine[component], wanted[component]
        likeness = (found[4] is None) == (other[4] is None) and (found[4] is None or abs(found[4] - other[4]) < 0.0006)
        if found[:4] != other[:4] or found[5] != other[5] or not likeness:
            differ.append(component)
    assert differ == expected["differ"]
    assert {kind: kinds[kind] for kind in ("entity", "chain")} == expected["forms"]
    assert sum(int(part.split(":")[1]) for row in mine.values() for part in row[5].split()) == expected["library"]
