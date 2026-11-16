/** Types of the JSON files and tables of a release, as docs/format.md defines them. */

/** `[x0, y0, x1, y1]` in units. */
export type Box = [number, number, number, number];

/** One contour: its pen commands and its points, x and y interleaved, in hundredths of a unit. */
export type Contour = [string, number[]];

export interface Glyph {
  contours: Contour[];
  pieces: number[][];
  box: Box;
  advance: number;
  /** GlyphWiki glyphs only: per stroke in KAGE order, its type (1 to 7) and the contours it drew. */
  strokes?: { type: number; contours: number[] }[];
}

export interface OutlineFile {
  format: string;
  font: string;
  licence: string;
  copyright: string;
  notice?: string;
  em: number;
  q: number;
  glyphs: Record<string, Glyph>;
}

export type CutStatus = "accepted" | "refused" | "reviewed-right" | "reviewed-wrong";
export type Tier = "source" | "machine" | "reviewed";
export type Division = "source" | "machine" | "reviewed" | "hand";
export type Style = "sans" | "serif" | "kaisho" | "fangsong" | "other";
export type Grain = "piece" | "contour";

/** One layer of a cut identifier: `<structure h8>-<method>:<path>`. */
export type Step = string;

export interface StrokeFile {
  format: string;
  font: string;
  licence: string;
  copyright: string;
  notice?: string;
  glyphs: Record<string, StrokeEntry[]>;
}

export interface StrokeEntry {
  /** The leaf cut the strokes divide. */
  cut: string;
  strokes: {
    type: string;
    method: "kage" | "lift" | "neck" | "graft";
    contours: number[];
    tier: Tier;
  }[];
  /** Per stroke cut at a seam, by its index in `strokes`: its own contours. */
  outline?: Record<string, Contour[]>;
}

export interface CheckResult {
  value: number;
  limit: number;
  pass: boolean;
  against?: string;
}

export interface CutEvidence {
  fit?: number;
  match?: number;
  margin?: number;
  agree?: number;
  reference?: number;
  referenceGlyph?: string;
}

export interface CutStyle {
  /** The component reference of the form the drawing matched. */
  member: string;
  basis: "kage" | "match" | "cluster" | "hand";
  likeness?: number;
  /** The glyph a `kage` cut was placed as, by its name: `glyphwiki@20261115/name.u793b-01`. */
  glyph?: string;
  tier: Tier;
}

export interface Cut {
  id: string;
  sig: string;
  /** Operand indices into the reading's structure. */
  path: number[];
  place: string;
  /** The node as the structure writes it: a class's canonical member, or a component in no class. */
  class: string;
  style?: CutStyle;
  contours: number[];
  box: Box;
  frame?: Box;
  gap?: number;
  area?: number;
  ink?: number;
  evidence?: CutEvidence;
  checks?: Record<string, CheckResult>;
  calibrated?: string | false;
  division: Division;
  status: CutStatus;
}

export interface ReadingMethod {
  name: "deal" | "lift" | "kage" | "axis" | "kanjivg" | "hand";
  tool: string;
  version?: string;
  commit?: string;
  grain: Grain;
}

export interface Reading {
  glyph: string;
  subject: string;
  /** The steps from the glyph to the cut this reading divides; empty for the glyph. */
  layer: Step[];
  /** `s.<h8>` of `text`. */
  structure: string;
  text: string;
  tree: string;
  opened?: { path: number[]; member: string; structure: string; text: string }[];
  method: ReadingMethod;
  complete: boolean;
  chosen: boolean;
  evidence?: Record<string, number>;
  cuts: Cut[];
}

export interface Skipped {
  subject: string;
  glyph?: string;
  layer: Step[];
  /** Absent where the text starts with no operator and so is no structure. */
  structure?: string;
  text: string;
  reason: { code: string; text: string };
}

export interface DrawnIds {
  structure: string;
  text: string;
  form: string;
  stroke?: string;
  strokeTier?: "machine" | "reviewed";
  /** The layers of the readings it is written from, the glyph's own first. */
  readings: Step[][];
  tier: "machine" | "reviewed";
  first: boolean;
}

export interface CutsFile {
  format: string;
  font: string;
  design: string;
  drawn: Record<string, DrawnIds[]>;
  readings: Reading[];
  skipped: Skipped[];
}

export interface FontEntry {
  id: string;
  name: string;
  version: string;
  nameVersion?: string;
  file: string;
  url: string;
  mirrors?: string[];
  sha256: string;
  archive?: { sha256: string; member: string };
  index?: number;
  instance?: Record<string, number>;
  upem: number;
  licence: string;
  licenceEvidence?: string;
  licenceFile?: string;
  copyright: string;
  reservedNames?: string[];
  style: Style;
  design: string;
  grain: Grain;
  /** GlyphWiki's row: the KAGE engine that draws the dump's glyphs. */
  renderer?: { engine: string; commit: string; style: string; route: string };
}

export interface DesignEntry {
  id: string;
  name: string;
  style: Style;
  /** Font identifiers in coverage order. */
  chain: string[];
  members: { font: string; evidence: string }[];
}

export interface FontsFile {
  format: string;
  fonts: FontEntry[];
  designs: DesignEntry[];
}

export interface FormEntry {
  cut: string;
  sig: string;
  basis: "reference" | "agree" | "single" | "kage" | "imported" | "hand";
  hosts?: number;
}

/** Class, then style: the cut chosen as that style's form in the design. */
export interface FormsFile {
  format: string;
  design: string;
  forms: Record<string, Record<string, FormEntry>>;
}

/** Class, style, place: cut identifiers, best first. */
export interface LibraryFile {
  format: string;
  design: string;
  library: Record<string, Record<string, Record<string, string[]>>>;
}

export interface Counts {
  readings: number;
  skipped: number;
  cuts: Partial<Record<CutStatus, number>>;
  structures: number;
  classes: number;
}

export interface Manifest {
  format: string;
  release: string;
  tool: { name: string; version: string; commit?: string };
  fonts: { id: string; sha256: string }[];
  counts: Record<string, Counts>;
  files: { path: string; bytes: number; sha256: string }[];
}

/** One row of `verdicts.tsv`. */
export interface VerdictRow {
  cut_id: string;
  sig: string;
  verdict: "" | "right" | "wrong";
  style: string;
  note: string;
  reviewer: string;
  at: string;
  release: string;
}

/** One row of `components.tsv`. */
export interface ComponentRow {
  component: string;
  kind: "character" | "subtree" | "ledger" | "numbered" | "entity" | "adobe-japan1";
  text: string;
  relation: "" | "glyph-of" | "equivalent";
  target: string;
  basis: string;
  tier: "" | "source" | "derived";
}

/** One row of `classes.tsv`. */
export interface ClassRow {
  member: string;
  target: string;
  canonical: string;
  place: string;
  basis: "radical-form" | "positional-form" | "unifiable-variant" | "radical-index" | "alignment" | "editorial";
  tier: "source" | "derived" | "editorial";
  note: string;
}
