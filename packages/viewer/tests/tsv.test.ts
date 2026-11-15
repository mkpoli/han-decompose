import { expect, test } from "bun:test";
import { gunzipIfNeeded, gunzipText } from "../src/lib/codec.ts";
import { cell, parseTable, tableRelease } from "../src/lib/tsv.ts";

test("a table has a format line, a header and rows", () => {
  const t = parseTable("# format=han-decompose/verdicts-tsv@1.0 release=v1\ncut_id\tsig\tnote\na\tb\t\nc\td\te\n");
  expect(t.columns).toEqual(["cut_id", "sig", "note"]);
  expect(t.rows).toEqual([
    { cut_id: "a", sig: "b", note: "" },
    { cut_id: "c", sig: "d", note: "e" },
  ]);
  expect(tableRelease(t.meta)).toBe("v1");
});

test("a table without a format line still reads", () => {
  expect(parseTable("a\tb\n1\t2\n").rows).toEqual([{ a: "1", b: "2" }]);
});

test("control characters leave a cell", () => {
  expect(cell(" a\tb\nc ")).toBe("a b c");
});

test("gzip is detected by its bytes and plain bytes pass through", async () => {
  const gz = new Uint8Array(await new Response(new Blob(["han 漢"]).stream().pipeThrough(new CompressionStream("gzip"))).arrayBuffer());
  expect(await gunzipText(gz)).toBe("han 漢");
  const plain = new TextEncoder().encode("plain");
  expect(await gunzipIfNeeded(plain)).toBe(plain);
});
