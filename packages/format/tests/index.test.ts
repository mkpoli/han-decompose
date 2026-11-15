import { expect, test } from "bun:test";

import manifest from "../package.json" with { type: "json" };
import { version } from "../src/index.js";

test("the package states its own version", () => {
  expect(version).toBe(manifest.version);
});
