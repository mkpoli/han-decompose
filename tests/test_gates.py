import numpy as np
import pytest

from han_decompose import descriptions, gates
from han_decompose import geometry as G
from han_decompose.cutters import deal
from han_decompose.gates import filled, skeleton
from han_decompose.pieces import Drawing

from .fonts import pinned_chain
from .test_pieces import box


def test_a_shape_is_stretched_to_the_grid_before_it_is_compared() -> None:
    tall, wide = filled.mask(box(0, 0, 100, 400)), filled.mask(box(0, 0, 900, 30))
    assert tall.shape == (filled.SIDE, filled.SIDE) and filled.iou(tall, wide) == 1.0
    ring = G.union_of([box(0, 0, 400, 100), box(0, 300, 400, 400), box(0, 0, 100, 400), box(300, 0, 400, 400)])
    assert 0 < filled.iou(filled.mask(ring), tall) < 1
    assert filled.iou(np.zeros((4, 4)), np.zeros((4, 4))) == 0.0


def test_thinning_leaves_a_line_one_pixel_wide() -> None:
    mask = np.zeros((32, 32), dtype=bool)
    mask[4:28, 13:19] = True
    line = skeleton.thin(mask)
    assert line.sum() > 0 and (line.sum(axis=1) <= 1).all() and (line & ~mask).sum() == 0


def test_the_skeleton_check_charges_only_for_what_a_cut_adds() -> None:
    bar = G.union_of([box(0, 0, 600, 100)])
    cross = G.union_of([box(0, 250, 600, 350), box(250, 0, 350, 600)])
    whole, part = skeleton.line(cross), skeleton.line(bar)
    assert skeleton.away(whole, whole) == 0.0
    # A bar stretched to its box is a horizontal line; against the cross it adds nothing of its own
    # kind, while the cross held against the bar adds its upright.
    assert skeleton.away(whole, part) > skeleton.away(part, whole)
    assert np.isnan(skeleton.away(np.zeros((0, 2)), whole))


def test_the_readings_of_ids_input_come_out_for_its_cuts() -> None:
    """Three 山 of ids-input's survey with the readings it wrote: 1 − IoU and the one-sided skeleton
    distance, each with the font of the 山 it was closest to."""
    try:
        table = descriptions.table("babelstone")
    except Exception:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    drawings = [Drawing(face) for face in pinned_chain("sans").faces]
    wanted = {
        "仙": [(0.2145, 0.0065, "noto-sans-cjk-jp@2.004")],
        "岸": [(0.4057, 0.0101, "plangothic-p2@2.9.5795")],
        "屾": [(0.4921, 0.0265, "plangothic-p2@2.9.5795"), (0.3489, 0.0152, "plangothic-p2@2.9.5795")],
    }
    for char, readings in wanted.items():
        description = table.first(char)
        glyph = drawings[0].glyph(f"U+{ord(char):04X}")
        assert description is not None and glyph is not None
        row = deal.read(
            glyph,
            drawings,
            description,
            description.tree(),
            table.glyph,
            whole=False,
            gate=gates.gate(table.glyph, "山"),
        )
        cuts = [cut for cut in row["cuts"] if cut["text"] == "山"]
        assert cuts and all(cut["calibrated"] == "u:5C71" and cut["status"] == "accepted" for cut in cuts)
        assert all("checks" not in cut for cut in row["cuts"] if cut["text"] != "山")
        found = [
            (cut["checks"]["filled"]["value"], cut["checks"]["skeleton"]["value"], cut["checks"]["filled"]["against"])
            for cut in cuts
        ]
        assert found == [(apart, away, f"{font}/U+5C71") for apart, away, font in readings]
        assert cuts[0]["checks"]["filled"]["limit"] == 0.6081 and cuts[0]["checks"]["skeleton"]["limit"] == 0.0499


def test_limits_are_borrowed_outside_the_fonts_and_the_component_they_were_set_on() -> None:
    try:
        table = descriptions.table("babelstone")
    except Exception:
        pytest.skip("The pinned tables are not in the cache; run `han-decompose fetch`.")
    sans = [Drawing(face) for face in pinned_chain("sans").faces]
    serif = [Drawing(face) for face in pinned_chain("serif").faces]
    description = table.first("仙")
    assert description is not None
    for drawings, calibrated in ((sans, ["u:5C71"]), (serif, [False])):
        glyph = drawings[0].glyph("U+4ED9")
        assert glyph is not None
        row = deal.read(
            glyph, drawings, description, description.tree(), table.glyph, whole=False, gate=gates.gate(table.glyph)
        )
        assert [cut["calibrated"] for cut in row["cuts"] if cut["text"] == "山"] == calibrated
        assert [cut["calibrated"] for cut in row["cuts"] if cut["text"] == "亻"] == [False]


def test_a_reading_past_a_limit_refuses_the_cut() -> None:
    assert gates._reading(0.0499, 0.0499, "f@1/U+5C71").passes is False
    assert gates._reading(0.04985, 0.0499, "f@1/U+5C71") == gates.Reading(0.0498, 0.0499, "f@1/U+5C71", True)
