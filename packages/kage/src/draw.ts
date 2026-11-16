import type { Engine, Kage } from "./engine.ts";

/** One placed component: a type-99 line, with what it drew. */
export interface Placement {
  /** Name of the glyph the line places. */
  glyph: string;
  /** Index of the placement that contains this one, or null. */
  parent: number | null;
  /** 0 for a line of the drawn glyph's own data. */
  depth: number;
  /** The line's box as placed in the drawn glyph's frame: x1, y1, x2, y2. */
  box: [number, number, number, number];
  /** The line's stretch columns (sx, sy, sx2, sy2) when it has any. */
  stretch: [number, number, number, number] | null;
  /** First and one-past-last stroke the placement expands to. */
  strokes: [number, number];
  /** First and one-past-last polygon (counting all strokes' polygons in order). */
  polygons: [number, number];
}

export interface DrawnStroke {
  type: number;
  polygons: [number, number][][];
}

export interface Drawn {
  name: string;
  upem: 200;
  frame: [number, number, number, number];
  strokes: DrawnStroke[];
  placements: Placement[];
  /** The glyph this one is an alias of: its data is one unstretched full-frame line. */
  alias: string | null;
  /** Placed names the dump does not hold; the engine skips them. */
  missing: string[];
}

export class DrawError extends Error {
  constructor(
    readonly reason: "no-data" | "too-deep" | "no-ink" | "engine",
    message: string,
  ) {
    super(message);
  }
}

const MAX_DEPTH = 24;

interface Node {
  glyph: string;
  box: [number, number, number, number];
  stretch: [number, number, number, number] | null;
  /** In the frame of the glyph that holds the line. */
  range: [number, number];
  children: Node[];
}

interface Expansion {
  strokes: number[][];
  nodes: Node[];
}

/**
 * `getEachStrokes` of kage.js at the pinned commit, unchanged in what it returns, which also
 * records the strokes each type-99 line expands to. Everything else (scaling, stretching)
 * is the engine's own `getEachStrokesOfBuhin`'s arithmetic, repeated here for the ranges.
 */
function expand(kage: Kage, glyphs: Map<string, string>, data: string, depth: number, missing: Set<string>): Expansion {
  if (depth > MAX_DEPTH) throw new DrawError("too-deep", "type-99 lines nest too deeply");
  const strokes: number[][] = [];
  const nodes: Node[] = [];
  for (const line of data.split("$")) {
    const c = line.split(":");
    if (Math.floor(Number(c[0])) !== 99) {
      strokes.push(Array.from({ length: 11 }, (_, k) => Math.floor(Number(c[k]))));
      continue;
    }
    const name = c[7] ?? "";
    const buhin = glyphs.get(name) ?? "";
    if (buhin === "") {
      missing.add(name);
      continue;
    }
    const x1 = Math.floor(Number(c[3]));
    const y1 = Math.floor(Number(c[4]));
    const x2 = Math.floor(Number(c[5]));
    const y2 = Math.floor(Number(c[6]));
    let sx = Math.floor(Number(c[1]));
    let sy = Math.floor(Number(c[2]));
    let sx2 = Math.floor(Number(c[9]));
    let sy2 = Math.floor(Number(c[10]));
    const stretch: Node["stretch"] = sx !== 0 || sy !== 0 ? [sx, sy, sx2, sy2] : null;
    const inner = expand(kage, glyphs, buhin, depth + 1, missing);
    const box = kage.getBox(inner.strokes);
    if (sx !== 0 || sy !== 0) {
      if (sx > 100) sx -= 200;
      else {
        sx2 = 0;
        sy2 = 0;
      }
    }
    const at = strokes.length;
    for (const s of inner.strokes) {
      if (sx !== 0 || sy !== 0) {
        s[3] = kage.stretch(sx, sx2, s[3], box.minX, box.maxX);
        s[4] = kage.stretch(sy, sy2, s[4], box.minY, box.maxY);
        s[5] = kage.stretch(sx, sx2, s[5], box.minX, box.maxX);
        s[6] = kage.stretch(sy, sy2, s[6], box.minY, box.maxY);
        if (s[0] !== 99) {
          s[7] = kage.stretch(sx, sx2, s[7], box.minX, box.maxX);
          s[8] = kage.stretch(sy, sy2, s[8], box.minY, box.maxY);
          s[9] = kage.stretch(sx, sx2, s[9], box.minX, box.maxX);
          s[10] = kage.stretch(sy, sy2, s[10], box.minY, box.maxY);
        }
      }
      const out = [s[0], s[1], s[2]] as number[];
      for (let k = 3; k <= 9; k += 2) {
        out.push(x1 + ((s[k] as number) * (x2 - x1)) / 200, y1 + ((s[k + 1] as number) * (y2 - y1)) / 200);
      }
      strokes.push(out);
    }
    nodes.push({
      glyph: name,
      box: [x1, y1, x2, y2],
      stretch,
      range: [at, strokes.length],
      children: shift(inner.nodes, at, [x1, y1, x2, y2]),
    });
  }
  return { strokes, nodes };
}

/** Moves a placed glyph's nodes into the frame and stroke numbering of the glyph that holds it. */
function shift(nodes: Node[], at: number, [x1, y1, x2, y2]: [number, number, number, number]): Node[] {
  return nodes.map((n) => ({
    glyph: n.glyph,
    stretch: n.stretch,
    box: [
      x1 + (n.box[0] * (x2 - x1)) / 200,
      y1 + (n.box[1] * (y2 - y1)) / 200,
      x1 + (n.box[2] * (x2 - x1)) / 200,
      y1 + (n.box[3] * (y2 - y1)) / 200,
    ],
    range: [n.range[0] + at, n.range[1] + at],
    children: shift(n.children, at, [x1, y1, x2, y2]),
  }));
}

/** Follows lines that place one glyph over the whole frame, without stretch. */
function aliasOf(glyphs: Map<string, string>, name: string): string | null {
  let at = name;
  const seen = new Set([name]);
  for (;;) {
    const data = glyphs.get(at) ?? "";
    const c = data.split(":");
    if (data.includes("$") || c[0] !== "99" || c.length < 8) return at === name ? null : at;
    const [, sx, sy, x1, y1, x2, y2, target] = c;
    if (!(sx === "0" && sy === "0" && x1 === "0" && y1 === "0" && x2 === "200" && y2 === "200") || !target)
      return at === name ? null : at;
    if (seen.has(target) || !glyphs.has(target)) return at === name ? null : at;
    seen.add(target);
    at = target;
  }
}

/** The adjusted stroke arrays `makeGlyph3` draws, as `getEachStrokes` then `adjustStrokes` give them. */
export function adjustedStrokes(engine: Engine, glyphs: Map<string, string>, name: string): number[][] {
  const kage = engine.newKage();
  const data = glyphs.get(name);
  if (data === undefined || data === "") throw new DrawError("no-data", `${name} has no data`);
  return kage.adjustStrokes(expand(kage, glyphs, data, 0, new Set()).strokes);
}

/** Draws a glyph the way `makeGlyph3` does and keeps what each placed component produced. */
export function drawGlyph(engine: Engine, glyphs: Map<string, string>, name: string): Drawn {
  const data = glyphs.get(name);
  if (data === undefined || data === "") throw new DrawError("no-data", `${name} has no data`);
  const kage = engine.newKage();
  const missing = new Set<string>();
  const { strokes: raw, nodes } = expand(kage, glyphs, data, 0, missing);
  const adjusted: number[][] = kage.adjustStrokes(raw);
  const strokes: DrawnStroke[] = [];
  const polygonStart: number[] = [];
  let count = 0;
  for (const s of adjusted) {
    const polygons = engine.newPolygons();
    try {
      engine.drawStroke(kage, polygons, s);
    } catch (e) {
      throw new DrawError("engine", `${name}: ${(e as Error).message}`);
    }
    polygonStart.push(count);
    const rounded = polygons.array.map((p) =>
      p.array.map((q): [number, number] => [Math.round(q.x * 1000) / 1000, Math.round(q.y * 1000) / 1000]),
    );
    count += rounded.length;
    strokes.push({ type: s[0] as number, polygons: rounded });
  }
  polygonStart.push(count);
  const placements: Placement[] = [];
  const walk = (list: Node[], parent: number | null, depth: number) => {
    for (const n of list) {
      const id = placements.length;
      placements.push({
        glyph: n.glyph,
        parent,
        depth,
        box: n.box,
        stretch: n.stretch,
        strokes: n.range,
        polygons: [polygonStart[n.range[0]] as number, polygonStart[n.range[1]] as number],
      });
      walk(n.children, id, depth + 1);
    }
  };
  walk(nodes, null, 0);
  if (count === 0) throw new DrawError("no-ink", `${name} draws no polygon`);
  return { name, upem: 200, frame: [0, 0, 200, 200], strokes, placements, alias: aliasOf(glyphs, name), missing: [...missing].sort() };
}
