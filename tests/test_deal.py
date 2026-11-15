import json
from collections.abc import Sequence
from typing import Literal

import numpy as np
import pytest

from han_decompose import descriptions, ids
from han_decompose import geometry as G
from han_decompose.cutters import deal, reading
from han_decompose.pieces import Drawing
from han_decompose.schema import Json, problems

from .conftest import FONT, GOLDEN
from .fonts import pinned_face
from .test_pieces import box

STACKS = GOLDEN.parent / "fixtures" / "stacks-on-shan.tsv"


def test_runs_keep_the_order_and_spreads_do_not() -> None:
    assert deal.runs([0, 1, 2], 2) == [[[0], [1, 2]], [[0, 1], [2]]]
    assert deal.runs([0, 1], 3) == []
    assert len(deal.spreads([0, 1, 2], 2)) == 6
    assert [[0], [1]] in deal.spreads([0, 1], 2) and [[1], [0]] in deal.spreads([0, 1], 2)


def test_a_fingerprint_reads_the_shape_whatever_its_size() -> None:
    small, large = box(0, 0, 100, 200), box(50, 50, 650, 250)
    first = deal.fingerprint(G.edges_of(small), small.bounds)
    second = deal.fingerprint(G.edges_of(large), large.bounds)
    assert first.shape == (deal.GRID * deal.GRID,) and deal.likeness(first, second) == 1.0
    half = deal.fingerprint(G.edges_of(box(0, 0, 50, 200)), small.bounds)
    assert deal.likeness(first, half) == 0.5
    assert deal.likeness(np.zeros(4), np.zeros(4)) == 0.0


def test_operands_of_a_row_follow_each_other_and_an_enclosure_wraps() -> None:
    assert deal.ordered((0, 0, 400, 800), (450, 0, 900, 800), "x")
    assert not deal.ordered((450, 0, 900, 800), (0, 0, 400, 800), "x")
    assert not deal.ordered((0, 0, 900, 800), (300, 0, 600, 800), "x")
    assert deal.ordered((0, 500, 900, 800), (0, 0, 900, 450), "y")
    assert not deal.ordered((0, 0, 900, 450), (0, 500, 900, 800), "y")
    assert deal.wraps((0, 0, 900, 800), (200, 0, 700, 600), deal.CLOSED["⿵"])
    assert not deal.wraps((200, 0, 700, 600), (0, 0, 900, 800), deal.CLOSED["⿵"])


def cached_table() -> descriptions.Table:
    try:
        return descriptions.table("babelstone")
    except Exception:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")


def test_the_golden_cuts_are_what_dealing_gives() -> None:
    golden = json.loads((GOLDEN / "cuts" / FONT / "babelstone" / "050.json").read_text(encoding="utf-8"))
    table, drawing = cached_table(), Drawing(pinned_face(FONT))
    glyph = drawing.glyph("U+50AC")
    description = table.first("催")
    assert glyph is not None and description is not None
    root = description.tree()
    inside = ids.parse("⿱山隹")
    root.children[1] = ids.Node("崔", inside.operator, inside.children, opened="⿱山隹")
    row = deal.read(glyph, [drawing], description, root, table.glyph)
    (wanted,) = golden["readings"]
    for key in ("glyph", "subject", "description", "ids", "tags", "tree", "opened", "complete"):
        assert row[key] == wanted[key]
    assert row["method"] == {
        "name": "deal",
        "tool": "han-decompose",
        "version": row["method"]["version"],
        "grain": "piece",
    }
    for cut, other in zip(row["cuts"], wanted["cuts"], strict=True):
        for key in ("id", "sig", "path", "place", "component", "text", "contours", "box", "frame", "status", "licence"):
            assert cut[key] == other[key]
        assert 0 < cut["evidence"]["fit"] <= 1
    # 亻 and 山 draw no window and may not come to enclose one; 隹 draws its own.
    assert [cut.get("checks") for cut in row["cuts"]] == [
        {"windows": {"value": 0, "limit": 1, "against": f"{FONT}/U+4EBB", "pass": True}},
        {"windows": {"value": 0, "limit": 1, "against": f"{FONT}/U+5C71", "pass": True}},
        None,
    ]
    assert 0 < row["evidence"]["likeness"] <= min(cut["evidence"]["fit"] for cut in row["cuts"])
    file = {**{key: golden[key] for key in ("format", "font", "source", "terms")}, "readings": [row], "skipped": []}
    outlines = json.loads((GOLDEN / "outlines" / FONT / "050.json").read_text(encoding="utf-8"))
    assert problems("cuts", file, outlines) == []


def test_a_glyph_with_fewer_pieces_than_operands_is_skipped() -> None:
    table, drawing = cached_table(), Drawing(pinned_face(FONT))
    glyph, description = drawing.glyph("U+5079"), table.first("偹")
    assert glyph is not None and description is not None
    with pytest.raises(deal.Skipped) as skipped:
        deal.read(glyph, [drawing], description, description.tree(), table.glyph)
    assert skipped.value.code == "too-few-pieces" and "2 pieces for 3 elements" in skipped.value.text


def test_the_stacks_on_shan_of_ids_input_reproduce() -> None:
    """ids-input's donor-parts.json: the 138 characters BabelStone describes as a stack standing on
    山, read in Noto Sans, then Jigmo, Jigmo2 and Jigmo3; 114 close. Each row of the fixture is a
    character, the font it was read in, the weakest agreement of its reading and how many pieces
    each leaf took."""
    table = cached_table()
    drawings = [
        Drawing(pinned_face(font))
        for font in ("noto-sans-cjk-jp@2.004", "jigmo@20250912", "jigmo2@20250912", "jigmo3@20250912")
    ]
    wanted = {}
    for line in STACKS.read_text(encoding="utf-8").splitlines()[1:]:
        char, font, score, numbers = line.split("\t")
        wanted[char] = (font, float(score), [int(number) for number in numbers.split(" ")])
    chosen = []
    for char, rows in table.rows.items():
        try:
            root = rows[0].tree()
        except ValueError:
            continue
        if root.operator in deal.STACKS and root.children[-1].text == "山":
            chosen.append(char)
    assert len(chosen) == 138
    found = {}
    for char in sorted(chosen):
        selector = f"U+{ord(char):04X}"
        description = table.first(char)
        assert description is not None
        for drawing in drawings:
            glyph = drawing.glyph(selector)
            if glyph is None:
                continue
            others = [drawing, *(other for other in drawings if other is not drawing)]
            try:
                row = deal.read(glyph, others, description, description.tree(), table.glyph)
            except deal.Skipped:
                continue
            if all(cut["status"] == "accepted" for cut in row["cuts"]):
                pieces = [
                    sum(1 for piece in glyph.members if set(piece) <= set(cut["contours"])) for cut in row["cuts"]
                ]
                found[char] = (drawing.id, row["evidence"]["likeness"], pieces)
                break
    assert set(found) == set(wanted)
    for char, (font, likeness, taken) in wanted.items():
        assert found[char][0] == font and abs(found[char][1] - likeness) < 0.0006 and found[char][2] == taken


def jigmo() -> tuple[descriptions.Table, list[Drawing]]:
    table = cached_table()
    return table, [Drawing(pinned_face(font)) for font in ("jigmo2@20250912", "jigmo@20250912")]


@pytest.mark.parametrize(
    ("char", "code"),
    [("\U00021d4d", "unlike-element"), ("\U00021d87", "layout-mismatch"), ("偹", "too-few-pieces")],
)
def test_a_glyph_that_does_not_close_is_skipped_with_its_reason(char: str, code: str) -> None:
    table, drawings = jigmo()
    if char == "偹":
        drawings = [Drawing(pinned_face(FONT))]
    glyph, description = drawings[0].glyph(f"U+{ord(char):04X}"), table.first(char)
    assert glyph is not None and description is not None
    with pytest.raises(deal.Skipped) as skipped:
        deal.read(glyph, drawings, description, description.tree(), table.glyph)
    assert skipped.value.code == code
    row = reading.skipped(description, skipped.value.code, skipped.value.text, f"{glyph.font}/{glyph.selector}")
    assert row["reason"] == {"code": code, "text": skipped.value.text} and row["subject"] == f"u:{ord(char):04X}"


def test_a_gate_decides_a_cut_and_names_what_its_limits_rest_on() -> None:
    table, drawing = cached_table(), Drawing(pinned_face(FONT))
    glyph, description = drawing.glyph("U+4ED9"), table.first("仙")
    assert glyph is not None and description is not None

    def gate(cutter: deal.Cutter, node: ids.Node, group: Sequence[int]) -> tuple[Json, str | Literal[False]] | None:
        if node.text != "山":
            return None
        return {"filled": {"value": 0.7, "limit": 0.6081, "against": f"{FONT}/U+5C71", "pass": False}}, "u:5C71"

    row = deal.read(glyph, [drawing], description, description.tree(), table.glyph, whole=False, gate=gate)
    left, right = row["cuts"]
    assert left["status"] == "accepted" and "checks" not in left and "calibrated" not in left
    assert right["status"] == "refused" and right["calibrated"] == "u:5C71" and set(right["checks"]) == {"filled"}
    assert "redrawn" not in row["evidence"] and left["frame"] == right["frame"]
    held = deal.read(glyph, [drawing], description, description.tree(), table.glyph)
    assert 0.4 <= held["evidence"]["redrawn"] <= 1 and set(held["cuts"][1]["checks"]) == {"windows"}


def test_the_fonts_start_with_the_glyphs_own() -> None:
    table, drawings = jigmo()
    glyph = Drawing(pinned_face(FONT)).glyph("U+4ED9")
    assert glyph is not None
    with pytest.raises(ValueError, match="start with the glyph's own"):
        deal.Cutter(glyph, drawings, table.glyph)
