import { expect, test } from "bun:test";
import { blockOf, blockOfRef, cutsPath, outlinePath } from "../src/lib/addressing.ts";

test("a block is the code point divided by 256, in lower hex of at least three digits", () => {
  expect(blockOf("U+50AC")).toBe("050");
  expect(blockOf("U+20B36")).toBe("20b");
  expect(blockOf("U+3400")).toBe("034");
  expect(blockOf("U+31AC3")).toBe("31a");
  expect(blockOf("U+F2A5")).toBe("0f2");
});

test("a variation sequence goes by its base and an index goes to gid", () => {
  expect(blockOf("U+845B.E0100")).toBe("084");
  expect(blockOf("gid.1234")).toBe("gid");
  expect(blockOf("not-a-selector")).toBeNull();
});

test("a subject that is no character is filed under gid", () => {
  expect(blockOfRef("u:5019")).toBe("050");
  expect(blockOfRef("u:845B.E0100")).toBe("084");
  expect(blockOfRef("bs:42")).toBe("gid");
  expect(blockOfRef("ids:⿱𰀪亻")).toBe("gid");
});

test("shard paths follow the layout", () => {
  expect(outlinePath("noto-sans-cjk-jp@2.004", "050")).toBe("outlines/noto-sans-cjk-jp@2.004/050.json.gz");
  expect(cutsPath("jigmo2@20250912", "chise", "20b")).toBe("cuts/jigmo2@20250912/chise/20b.json.gz");
});
