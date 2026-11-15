/** Reading a reading: which cut owns which contour, and the colour of each node. */
import type { Cut, Reading } from "han-decompose";

export const NODE_COLOURS = 8;

export const pathKey = (path: number[]): string => path.join(".");

function comparePaths(a: number[], b: number[]): number {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d) return d;
  }
  return a.length - b.length;
}

/** Cuts in path order. */
export const byPath = (cuts: Cut[]): Cut[] => [...cuts].sort((a, b) => comparePaths(a.path, b.path));

/** The colour index (0-based, cycling) of each node, by its place in path order. */
export function nodeIndex(reading: Pick<Reading, "cuts">): Map<string, number> {
  const out = new Map<string, number>();
  byPath(reading.cuts).forEach((cut, i) => out.set(pathKey(cut.path), i % NODE_COLOURS));
  return out;
}

/** The CSS colour of a node index. */
export const nodeColour = (index: number): string => `var(--hd-node-${(index % NODE_COLOURS) + 1})`;

/** For every contour the deepest cut that holds it. */
export function contourOwner(reading: Pick<Reading, "cuts">): Map<number, Cut> {
  const owner = new Map<number, Cut>();
  for (const cut of byPath(reading.cuts)) {
    for (const index of cut.contours) {
      const held = owner.get(index);
      if (!held || cut.path.length >= held.path.length) owner.set(index, cut);
    }
  }
  return owner;
}

export interface Layer {
  cut: Cut;
  contours: number[];
}

/** The contours each cut paints, so that a contour is painted once: by the deepest cut that holds it. */
export function layers(reading: Pick<Reading, "cuts">): Layer[] {
  const owner = contourOwner(reading);
  const by = new Map<string, Layer>();
  for (const cut of byPath(reading.cuts)) by.set(cut.id, { cut, contours: [] });
  for (const [index, cut] of [...owner].sort((a, b) => a[0] - b[0])) by.get(cut.id)?.contours.push(index);
  return [...by.values()].filter((l) => l.contours.length > 0);
}

export const isRefused = (cut: Cut): boolean => cut.status === "refused";

/** The number a cut is ranked by: its `fit`, or its `match` where it has none. */
export const score = (cut: Pick<Cut, "evidence">): number | undefined => cut.evidence?.fit ?? cut.evidence?.match;

/** The size of a cut: its area, or the area of its box. */
export function size(cut: Pick<Cut, "area" | "box">): number {
  if (cut.area !== undefined) return cut.area;
  return Math.max(cut.box[2] - cut.box[0], 0) * Math.max(cut.box[3] - cut.box[1], 0);
}
