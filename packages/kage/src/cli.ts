import { readFileSync } from "node:fs";
import { drawGlyph, DrawError } from "./draw.ts";
import { readDump } from "./dump.ts";
import { loadEngine } from "./engine.ts";

/**
 * Reads glyph names (one per line) from stdin or `--list FILE` and writes one JSON line per glyph:
 * the drawing, or {name, error: {reason, message}}.
 *
 *   bun packages/kage/src/cli.ts --dump dump_newest_only.txt [--dump versions.txt] [--engine DIR] [--list FILE]
 */
const args = process.argv.slice(2);
const option = (flag: string): string | undefined => {
  const i = args.indexOf(flag);
  return i >= 0 ? args[i + 1] : undefined;
};

const dumps = args.flatMap((a, i) => (a === "--dump" && args[i + 1] ? [args[i + 1] as string] : []));
if (dumps.length === 0) {
  console.error("usage: cli.ts --dump DUMP [--dump MORE] [--engine DIR] [--list FILE]  (names on stdin)");
  process.exit(2);
}
const list = option("--list");
const input = list ? readFileSync(list, "utf8") : await Bun.stdin.text();
const names = input.split("\n").map((s) => s.trim()).filter((s) => s !== "");

const engine = loadEngine(option("--engine"));
const glyphs = await readDump(...dumps);

const out: string[] = [];
const flush = () => {
  if (out.length) process.stdout.write(`${out.join("\n")}\n`);
  out.length = 0;
};
for (const name of names) {
  try {
    out.push(JSON.stringify(drawGlyph(engine, glyphs, name)));
  } catch (e) {
    const reason = e instanceof DrawError ? e.reason : "engine";
    out.push(JSON.stringify({ name, error: { reason, message: (e as Error).message } }));
  }
  if (out.length >= 200) flush();
}
flush();
