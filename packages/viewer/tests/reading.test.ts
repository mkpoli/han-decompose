import { expect, test } from "bun:test";
import type { Cut } from "../src/lib/format1";
import { contourOwner, layers, nodeColour, nodeIndex, score, size } from "../src/lib/reading.ts";

const cut = (id: string, path: number[], contours: number[], extra: Partial<Cut> = {}): Cut =>
  ({ id, sig: "0", path, place: "", component: "u:4E00", text: "一", contours, box: [0, 0, 10, 20], status: "accepted", licence: { outline: "", description: "" }, ...extra }) as Cut;

const reading = { cuts: [cut("c11", [1, 1], [3, 4]), cut("c0", [0], [0, 1]), cut("c1", [1], [2, 3, 4]), cut("c10", [1, 0], [2])] };

test("colours follow the path order of the reading", () => {
  const index = nodeIndex(reading);
  expect(index.get("0")).toBe(0);
  expect(index.get("1")).toBe(1);
  expect(index.get("1.0")).toBe(2);
  expect(index.get("1.1")).toBe(3);
  expect(nodeColour(0)).toBe("var(--hd-node-1)");
  expect(nodeColour(9)).toBe("var(--hd-node-2)");
});

test("a contour belongs to the deepest cut that holds it", () => {
  const owner = contourOwner(reading);
  expect(owner.get(2)?.id).toBe("c10");
  expect(owner.get(3)?.id).toBe("c11");
  expect(owner.get(0)?.id).toBe("c0");
  expect(owner.has(5)).toBe(false);
});

test("a layer holds the contours its cut paints", () => {
  expect(layers(reading).map((l) => [l.cut.id, l.contours])).toEqual([
    ["c0", [0, 1]],
    ["c10", [2]],
    ["c11", [3, 4]],
  ]);
});

test("a cut is ranked by fit, or by match where it has no fit, and sized by area or by box", () => {
  expect(score({ evidence: { fit: 0.5, match: 0.9 } })).toBe(0.5);
  expect(score({ evidence: { match: 0.9 } })).toBe(0.9);
  expect(score({})).toBeUndefined();
  expect(size({ area: 12, box: [0, 0, 10, 20] })).toBe(12);
  expect(size({ box: [0, 0, 10, 20] })).toBe(200);
});
