"""Cut 萬 into the parts its description names, and draw them.

萬 is ⿱艹禺, and 禺 is ⿱田禸. The same cutter that cuts a 山 out of its characters
reads 萬 the same way: the font's own untouching pieces, dealt to the elements the
description names, each piece whole. The output is one SVG per face and a JSON of the
parts, so a reader can see where the 禸 sits inside 萬's frame.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pathops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_donor_parts as base  # noqa: E402
from build_mountain_instances import Enclosing  # noqa: E402

CHAR = "萬"
OUT = ROOT / ".local" / "wan"

def to_path_commands(shape: pathops.Path):
    return base.commands_of(shape)

def main() -> int:
    table, labels = base.read_table(), base.read_labels()
    faces = base.load_faces([], ROOT / "cache", False)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for face in faces:
        pieces = face.pieces(CHAR)
        if not pieces:
            continue
        ids = table[CHAR][0]
        root = base.parse(ids)
        cutter = Enclosing(pieces, labels, faces)
        try:
            cut = cutter.cut(root, list(range(len(pieces))))
        except base.Skipped as why:
            report[face.name] = {"error": str(why)}
            continue
        parts = []
        for node, group in cut:
            shape = base.union_of([pieces[i] for i in group])
            parts.append({
                "leaf": base.glyph_of(node.text, labels),
                "element": node.text,
                "pieces": group,
                "box": [round(v, 1) for v in shape.bounds],
                "area": round(abs(shape.area), 1),
                "path": to_path_commands(shape),
            })
        report[face.name] = {"ids": ids, "pieces": len(pieces), "parts": parts}
    (OUT / "wan-parts.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    for name, found in report.items():
        if "error" in found:
            print(f"{name}: {found['error']}")
        else:
            print(f"{name}: {found['pieces']} pieces -> " +
                  ", ".join(f"{p['element']}({p['leaf']})" for p in found["parts"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
