import { expect, test } from "bun:test";
import type { Glyph } from "han-decompose";
import { boxViewBox, contourPath, contoursPath } from "../src/lib/path.ts";

test("a polygon is drawn in units with y flipped", () => {
  expect(contourPath(["MLLL", [0, 0, 10000, 0, 10000, 50000, 0, 50000]])).toBe("M0 0L100 0L100 -500L0 -500Z");
});

test("a quadratic run with several off-curve points implies the on-curve points between them", () => {
  expect(contourPath(["MQ3", [0, 0, 10000, 10000, 20000, 10000, 30000, 0]])).toBe("M0 0Q100 -100 150 -100Q200 -100 300 0Z");
});

test("a single off-curve point ends at the on-curve point", () => {
  expect(contourPath(["MQ2L", [0, 0, 5000, 5000, 10000, 0, 0, 0]])).toBe("M0 0Q50 -50 100 0L0 0Z");
});

test("a contour of off-curve points alone is a closed run", () => {
  expect(contourPath(["Q4*", [0, 0, 10000, 0, 10000, 10000, 0, 10000]])).toBe("M0 -50Q0 0 50 0Q100 0 100 -50Q100 -100 50 -100Q0 -100 0 -50Z");
});

test("a cubic takes two controls and an end", () => {
  expect(contourPath(["MC", [0, 0, 1000, 2000, 3000, 4000, 5000, 0]])).toBe("M0 0C10 -20 30 -40 50 0Z");
});

test("numbers carry at most two decimals", () => {
  expect(contourPath(["ML", [1, 0, 33333, 0]])).toBe("M0.01 0L333.33 0Z");
});

test("a set of contours is one path, so a counter cuts out", () => {
  const glyph: Glyph = { contours: [["ML", [0, 0, 100, 0]], ["ML", [0, 0, 200, 0]], ["ML", [0, 0, 300, 0]]], pieces: [[0, 1, 2]], box: [0, 0, 3, 0], advance: 1000 };
  expect(contoursPath(glyph)).toBe("M0 0L1 0ZM0 0L2 0ZM0 0L3 0Z");
  expect(contoursPath(glyph, [2, 0])).toBe("M0 0L3 0ZM0 0L1 0Z");
});

test("a box gets a square view with room around it", () => {
  expect(boxViewBox([100, 0, 300, 100], 0)).toBe("100 -150 200 200");
});
