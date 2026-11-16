"""Move the chosen stroke cut from the comparison lab into the review data.

The comparison lab writes every method it tried; the notch-pair neck cut reads cleanest,
so its regions become each entry's `strokeParts`, in stroke order.

Run: uv run --with skimage --with shapely --with scipy python scripts/adopt_neck_cut.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "demo" / "donor-strokes-lab.json"
REVIEW = ROOT / "demo" / "donor-parts-review.json"
METHOD = "neckcut"

lab = json.loads(LAB.read_text())
review = json.loads(REVIEW.read_text())
chosen = {}
for entry in lab["entries"]:
    method = next(m for m in entry["methods"] if m["key"] == METHOD)
    chosen[entry["char"]] = method["parts"]

missing = []
for entry in review["entries"]:
    parts = chosen.get(entry["char"])
    if parts is None:
        missing.append(entry["char"])
        continue
    entry["strokeParts"] = parts
REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n")
print("adopted", len(chosen), "characters, missing", ", ".join(missing) or "none")
print("strokes for 㞪", sum(len(g["strokes"]) for g in chosen["㞪"]))
