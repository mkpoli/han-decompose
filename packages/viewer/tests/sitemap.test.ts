import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { parseRoute } from "../src/lib/router.ts";

const read = (name: string): string => readFileSync(new URL(`../public/${name}`, import.meta.url), "utf8");

test("robots.txt names the sitemap", () => {
  expect(read("robots.txt")).toContain("Sitemap: https://decompose.mkpo.li/sitemap.xml");
});

test("the sitemap lists only routes the viewer has", () => {
  const paths = [...read("sitemap.xml").matchAll(/<loc>https:\/\/decompose\.mkpo\.li(\/[^<]*)<\/loc>/g)].map((m) => m[1] ?? "");
  expect(paths).toEqual(["/", "/skipped", "/review"]);
  for (const path of paths) expect(parseRoute(path).name).not.toBe("missing");
});
