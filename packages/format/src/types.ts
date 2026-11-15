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
  importedFrom?: string;
}

export interface Cut {
  id: string;
  sig: string;
  path: number[];
  place: string;
  component: string;
  text: string;
  contours: number[];
  box: Box;
  frame?: Box;
  gap?: number;
  area?: number;
  ink?: number;
  evidence?: CutEvidence;
  checks?: Record<string, CheckResult>;
  calibrated?: string | false;
  status: CutStatus;
  licence: { outline: string; description: string; guide?: string };
}

export interface ReadingMethod {
  name: string;
  tool?: string;
  version?: string;
  commit?: string;
  grain?: "piece" | "contour";
  guide?: string;
}

export interface Reading {
  glyph: string;
  subject: string;
  description: string;
  ids: string;
  tags?: string;
  tree: string;
  opened?: { path: number[]; component: string; description: string; ids: string }[];
  method: ReadingMethod;
  complete: boolean;
  evidence?: Record<string, number>;
  cuts: Cut[];
}

export interface Skipped {
  subject: string;
  glyph?: string;
  description: string;
  ids: string;
  tags?: string;
  reason: { code: string; text: string };
}

export interface CutsFile {
  format: string;
  font: string;
  source: string;
  terms: { outline: string; description: string; guide?: string; notices: string[] };
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
  style: "sans" | "serif" | "kaisho" | "fangsong" | "other";
}

export interface FontsFile {
  format: string;
  chains: Record<string, string[]>;
  fonts: FontEntry[];
}

export interface SourceEntry {
  id: string;
  name: string;
  role: "description" | "guide" | "reference" | "identity" | "cuts";
  url: string;
  pin: string;
  retrieved: string;
  licence: string;
  licenceEvidence?: string;
  licenceFile?: string;
  attribution: string;
  weakness?: string;
}

export interface SourcesFile {
  format: string;
  sources: SourceEntry[];
}

export interface FormEntry {
  cut: string;
  sig: string;
  basis: "reference" | "agree" | "single" | "imported" | "hand";
  hosts?: number;
}

export interface FormsFile {
  format: string;
  chain: string;
  forms: Record<string, FormEntry>;
}

export interface LibraryFile {
  format: string;
  chain: string;
  library: Record<string, Record<string, string[]>>;
}

export interface Counts {
  readings: number;
  skipped: number;
  components: number;
  cuts: Partial<Record<CutStatus, number>>;
}

export interface Manifest {
  format: string;
  release: string;
  tool: { name: string; version: string; commit?: string };
  fonts: unknown;
  sources: unknown;
  counts: Record<string, Record<string, Partial<Counts>>>;
  files: { path: string; bytes: number; sha256: string }[];
}

/** One row of `verdicts.tsv`. */
export interface VerdictRow {
  cut_id: string;
  sig: string;
  verdict: "right" | "wrong";
  note: string;
  reviewer: string;
  at: string;
  release: string;
}
