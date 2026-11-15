/** Drawing outlines: pen commands to SVG paths, in units with y flipped. */
import type { Box, Contour, Glyph } from "han-decompose";

const TOKEN = /M|L|C|Q(\d+)(\*?)/g;

const num = (value: number): string => {
  const text = (Math.round(value * 100) / 100).toFixed(2).replace(/\.?0+$/, "");
  return text === "-0" ? "0" : text;
};

type Point = [number, number];

/** One contour as an SVG path: the em is 1000 units, y is flipped so that up is negative. */
export function contourPath([commands, points]: Contour): string {
  let at = 0;
  const take = (): Point => {
    const p: Point = [(points[at] ?? 0) / 100, -(points[at + 1] ?? 0) / 100];
    at += 2;
    return p;
  };
  const mid = (a: Point, b: Point): Point => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const xy = (p: Point): string => `${num(p[0])} ${num(p[1])}`;
  let out = "";
  for (const match of commands.matchAll(TOKEN)) {
    const op = match[0][0];
    if (op === "M") out += `M${xy(take())}`;
    else if (op === "L") out += `L${xy(take())}`;
    else if (op === "C") {
      const a = take();
      const b = take();
      const c = take();
      out += `C${xy(a)} ${xy(b)} ${xy(c)}`;
    } else {
      const n = Number(match[1]);
      if (match[2] === "*") {
        const offs = Array.from({ length: n }, take);
        const last = offs[n - 1];
        const first = offs[0];
        if (!last || !first) continue;
        out += `M${xy(mid(last, first))}`;
        for (let k = 0; k < n; k++) {
          const off = offs[k]!;
          out += `Q${xy(off)} ${xy(mid(off, offs[(k + 1) % n]!))}`;
        }
      } else if (n === 1) out += `L${xy(take())}`;
      else {
        const offs = Array.from({ length: n - 1 }, take);
        const end = take();
        offs.forEach((off, k) => {
          out += `Q${xy(off)} ${xy(k < offs.length - 1 ? mid(off, offs[k + 1]!) : end)}`;
        });
      }
    }
  }
  return `${out}Z`;
}

/** Several contours as one path, so that counters inside the set cut out of it. */
export function contoursPath(glyph: Glyph, indices?: Iterable<number>): string {
  const wanted = indices ? [...indices] : glyph.contours.map((_, i) => i);
  return wanted
    .map((i) => glyph.contours[i])
    .filter((c): c is Contour => c !== undefined)
    .map(contourPath)
    .join("");
}

/** The em square of a glyph, y flipped: baseline at 0, ascent to 880 above it. */
export const EM_VIEWBOX = "0 -880 1000 1000";

/** A view box around a box (units, y up), with room on every side. */
export function boxViewBox(box: Box, pad = 40): string {
  const [x0, y0, x1, y1] = box;
  const w = Math.max(x1 - x0, 1) + pad * 2;
  const h = Math.max(y1 - y0, 1) + pad * 2;
  const side = Math.max(w, h);
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  return `${num(cx - side / 2)} ${num(-cy - side / 2)} ${num(side)} ${num(side)}`;
}
