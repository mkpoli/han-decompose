import { expect, test } from "bun:test";

import manifest from "../package.json" with { type: "json" };
import { type CutsFile, version } from "../src/index.js";

test("the package states its own version", () => {
  expect(version).toBe(manifest.version);
});

test("the golden cut file reads as the types describe it", async () => {
  const golden = "../../../tests/golden/cuts/noto-sans-cjk-jp@2.004/050.json";
  const cuts = (await Bun.file(new URL(golden, import.meta.url)).json()) as CutsFile;
  const [root, inner] = cuts.readings;
  expect(cuts.design).toBe("source-han-sans");
  expect(root?.layer).toEqual([]);
  expect(inner?.layer).toEqual([root?.cuts[1]?.id.split("~")[1] ?? ""]);
  expect(cuts.drawn["U+50AC"]?.[0]?.first).toBe(true);
  for (const cut of [...(root?.cuts ?? []), ...(inner?.cuts ?? [])]) {
    expect(cut.id.startsWith(root?.glyph ?? "")).toBe(true);
    expect(cut.division).toBe("hand");
  }
});
