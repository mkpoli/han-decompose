import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import pin from "../pin.json" with { type: "json" };

/** The engine's own object, which has no types. */
// biome-ignore lint/suspicious/noExplicitAny: the engine is plain JavaScript
export type Kage = any;

export interface Engine {
  newKage(): Kage;
  newPolygons(): { array: { array: { x: number; y: number }[] }[] };
  drawStroke(kage: Kage, polygons: unknown, stroke: number[]): void;
}

export const ENGINE_COMMIT = pin.commit;

export function defaultEngineDir(): string {
  const cache = process.env["HAN_DECOMPOSE_CACHE"] ?? join(homedir(), ".cache", "han-decompose");
  return join(cache, "glyphwiki", `kage-engine-${pin.commit.slice(0, 8)}`);
}

/** Clones the pinned commit into `dir` when it is not there yet. */
export function fetchEngine(dir: string): void {
  if (existsSync(join(dir, "kage.js"))) return;
  const run = (args: string[]) => {
    const r = Bun.spawnSync(["git", ...args], { stderr: "pipe" });
    if (!r.success) throw new Error(`git ${args.join(" ")}: ${r.stderr.toString()}`);
  };
  run(["clone", "--quiet", "--no-checkout", pin.repository, dir]);
  run(["-C", dir, "checkout", "--quiet", pin.commit]);
}

const ORDER = ["2d.js", "buhin.js", "curve.js", "kage.js", "kagecd.js", "kagedf.js", "polygon.js", "polygons.js"] as const;

/** Loads the engine scripts from `dir` after checking each against the pinned SHA-256. */
export function loadEngine(dir: string = defaultEngineDir()): Engine {
  fetchEngine(dir);
  const files = pin.files as Record<string, string>;
  let source = "";
  for (const name of ORDER) {
    const text = readFileSync(join(dir, name));
    const digest = createHash("sha256").update(text).digest("hex");
    if (digest !== files[name]) throw new Error(`${name} differs from the pinned kage-engine ${pin.commit}`);
    source += `${text.toString("utf8")}\n`;
  }
  const make = new Function(
    `${source}\nreturn { Kage, Polygons, dfDrawFont };`,
  ) as () => { Kage: new () => Kage; Polygons: new () => never; dfDrawFont: (...a: unknown[]) => void };
  const { Kage, Polygons, dfDrawFont } = make();
  return {
    newKage: () => new Kage(),
    newPolygons: () => new Polygons(),
    drawStroke: (kage, polygons, s) =>
      dfDrawFont(kage, polygons, s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], s[9], s[10]),
  };
}
