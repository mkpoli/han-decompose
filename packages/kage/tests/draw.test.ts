import { expect, test } from "bun:test";
import { adjustedStrokes, drawGlyph } from "../src/draw.ts";
import { readDump } from "../src/dump.ts";
import { loadEngine } from "../src/engine.ts";

const engine = loadEngine();
const glyphs = await readDump(new URL("../../../tests/fixtures/glyphwiki/dump.txt", import.meta.url).pathname);

test("reads name to data and skips header, rule and count", () => {
  expect(glyphs.get("u793e-j")).toBe("99:0:0:0:0:180:200:u793b-01$99:0:0:64:0:197:200:u571f-j");
  expect(glyphs.has("name")).toBe(false);
  expect(glyphs.size).toBe(20);
});

test("社 resolves through its alias to the placements of 礻 and 土", () => {
  const d = drawGlyph(engine, glyphs, "u793e");
  expect(d.alias).toBe("u793e-j");
  expect(d.placements.map((p) => [p.glyph, p.parent, p.depth])).toEqual([
    ["u793e-j", null, 0],
    ["u793b-01", 0, 1],
    ["u571f-j", 0, 1],
  ]);
  const [left, earth] = [d.placements[1], d.placements[2]];
  expect(left?.box).toEqual([0, 0, 180, 200]);
  expect(earth?.box).toEqual([64, 0, 197, 200]);
  expect(left?.strokes).toEqual([0, 5]);
  expect(earth?.strokes).toEqual([5, 8]);
});

test("strokes are grouped: one entry per stroke, with its own polygons", () => {
  const d = drawGlyph(engine, glyphs, "u793e");
  expect(d.strokes.map((s) => s.type)).toEqual([1, 1, 2, 1, 2, 1, 1, 1]);
  for (const s of d.strokes) expect(s.polygons.length).toBeGreaterThan(0);
  const total = d.strokes.reduce((n, s) => n + s.polygons.length, 0);
  expect(d.placements[0]?.polygons).toEqual([0, total]);
  expect(d.placements[1]?.polygons[1]).toBe(d.placements[2]?.polygons[0] as number);
});

test("a glyph of raw strokes has no placements", () => {
  const d = drawGlyph(engine, glyphs, "u793a-01");
  expect(d.placements).toEqual([]);
  expect(d.alias).toBeNull();
  expect(d.strokes).toHaveLength(5);
});

test("the expansion matches the engine's own getEachStrokes and makeGlyph3", () => {
  for (const name of ["u793e", "u845b-ue0100", "u793b-01"]) {
    const kage = engine.newKage();
    for (const [k, v] of glyphs) kage.kBuhin.set(k, v);
    const own = adjustedStrokes(engine, glyphs, name);
    const theirs = kage.adjustStrokes(kage.getEachStrokes(glyphs.get(name)));
    expect(own).toEqual(theirs);
    const polys = kage.makeGlyph3(glyphs.get(name) as string);
    const drawn = drawGlyph(engine, glyphs, name);
    expect(drawn.strokes.map((s) => s.polygons.length)).toEqual(polys.map((p: { array: unknown[] }) => p.array.length));
  }
});

test("an IVS glyph places the component glyphs of its form", () => {
  const d = drawGlyph(engine, glyphs, "u845b-ue0100");
  expect(d.placements.map((p) => p.glyph)).toEqual(["u8279-03", "u66f7-var-002"]);
});

test("the related field is not read", () => {
  // u793e's related is u3013 in the dump, and no placement names it
  const d = drawGlyph(engine, glyphs, "u793e");
  expect(d.placements.some((p) => p.glyph === "u3013")).toBe(false);
});

test("a placed glyph the dump lacks is reported and skipped", () => {
  expect(() => drawGlyph(engine, glyphs, "u793a")).toThrow("draws no polygon");
  const d = drawGlyph(engine, glyphs, "u845b");
  expect(d.missing).toEqual(["u66f7-j"]);
  expect(d.placements.map((p) => p.glyph)).toEqual(["u8279-03"]);
});

test("glyphs that place each other are refused", () => {
  const loop = new Map([
    ["a", "99:0:0:0:0:200:200:b$1:0:0:1:1:2:2"],
    ["b", "99:0:0:0:0:200:200:a$99:0:0:0:0:200:200:a"],
  ]);
  expect(() => drawGlyph(engine, loop, "a")).toThrow("a > b > a");
});

test("a stretched placement's box follows the engine's stretch and holds its ink", () => {
  // u5001-j places 知 with stretch columns (160, 0, …, -35, 0); the engine squeezes its left edge
  const d = drawGlyph(engine, glyphs, "u5001-j");
  const child = d.placements.find((p) => p.glyph === "u77e2-08");
  const [x1, , x2] = child?.box ?? [0, 0, 0, 0];
  expect(x1).toBeCloseTo(55.41, 1);
  expect(x2).toBeCloseTo(173.57, 1);
  const ink = child?.ink;
  expect(ink).not.toBeNull();
  expect(ink?.[0] as number).toBeGreaterThan(x1 - 4);
  expect(ink?.[2] as number).toBeLessThan(x2);
  expect(ink?.[0]).toBeCloseTo(52.7, 1);
  expect(ink?.[2]).toBeCloseTo(125, 0);
});
