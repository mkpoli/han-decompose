import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const content = (selector: RegExp): string | undefined => selector.exec(html)?.[1];

test("the page names itself for a crawler", () => {
  const description = content(/<meta name="description" content="([^"]+)"/);
  expect(description).toBeTruthy();
  expect(content(/<link rel="canonical" href="([^"]+)"/)).toBe("https://decompose.mkpo.li/");
  expect(content(/<meta property="og:title" content="([^"]+)"/)).toBe("Han Decompose");
  expect(content(/<meta property="og:description" content="([^"]+)"/)).toBe(description);
  expect(content(/<meta property="og:url" content="([^"]+)"/)).toBe("https://decompose.mkpo.li/");
});
