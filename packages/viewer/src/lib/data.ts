/** The one module that fetches a release: files, caching and shard addressing. */
import type { Counts, CutsFile, FontEntry, FontsFile, FormsFile, Glyph, LibraryFile, Manifest, OutlineFile, SourceEntry, SourcesFile, VerdictRow } from "han-decompose";
import { blockOf, blockOfRef, componentsTablePath, cutsPath, cutsTablePath, formsPath, libraryPath, outlinePath, skippedTablePath } from "./addressing.ts";
import { gunzipIfNeeded } from "./codec.ts";
import { parseCutId } from "./ids.ts";
import { parseTable, type Table } from "./tsv.ts";

const BASE = `${import.meta.env.BASE_URL}data/`;

const files = new Map<string, Promise<Uint8Array | null>>();

/** The bytes of a release file, or null where the release has none. A host that answers a miss with the app is a miss. */
function bytes(path: string): Promise<Uint8Array | null> {
  let held = files.get(path);
  if (!held) {
    held = (async () => {
      try {
        const response = await fetch(BASE + path);
        if (!response.ok) return null;
        if ((response.headers.get("content-type") ?? "").includes("text/html")) return null;
        return await gunzipIfNeeded(new Uint8Array(await response.arrayBuffer()));
      } catch {
        return null;
      }
    })();
    files.set(path, held);
  }
  return held;
}

const parsed = new Map<string, Promise<unknown>>();

function cached<T>(path: string, read: (data: Uint8Array) => T): Promise<T | null> {
  let held = parsed.get(path) as Promise<T | null> | undefined;
  if (!held) {
    held = bytes(path).then((data) => (data ? read(data) : null));
    parsed.set(path, held);
  }
  return held;
}

const decoder = new TextDecoder();
const json = <T>(path: string): Promise<T | null> => cached(path, (data) => JSON.parse(decoder.decode(data)) as T);
const table = (path: string): Promise<Table | null> => cached(path, (data) => parseTable(decoder.decode(data)));

export interface Release {
  manifest: Manifest;
  fonts: FontsFile;
  sources: SourcesFile;
}

let releasePromise: Promise<Release> | null = null;

/** The release's manifest, fonts and sources; rejects where there is no release at `/data/`. */
export function release(): Promise<Release> {
  releasePromise ??= (async () => {
    const [manifest, fonts, sources] = await Promise.all([json<Manifest>("manifest.json"), json<FontsFile>("fonts.json"), json<SourcesFile>("sources.json")]);
    if (!manifest || !fonts || !sources) throw new Error("no release");
    return { manifest, fonts, sources };
  })();
  return releasePromise;
}

export const fontOf = (rel: Release, id: string): FontEntry | undefined => rel.fonts.fonts.find((f) => f.id === id);
export const sourceOf = (rel: Release, id: string): SourceEntry | undefined => rel.sources.sources.find((s) => s.id === id);

/** The chain a font belongs to, if any. */
export const chainOf = (rel: Release, font: string): string | undefined => Object.entries(rel.fonts.chains).find(([, ids]) => ids.includes(font))?.[0];

/** The fonts that are in a chain, in chain order. */
export function chainFonts(rel: Release): { chain: string; fonts: FontEntry[] }[] {
  return Object.entries(rel.fonts.chains).map(([chain, ids]) => ({ chain, fonts: ids.map((id) => fontOf(rel, id)).filter((f): f is FontEntry => f !== undefined) }));
}

/** The sources a font has anything for. */
export const sourcesOfFont = (rel: Release, font: string): string[] => Object.keys(rel.manifest.counts[font] ?? {});

export function outlineShard(font: string, block: string): Promise<OutlineFile | null> {
  return json<OutlineFile>(outlinePath(font, block));
}

/** One glyph of a font, or null where the font has none in the release. */
export async function glyph(font: string, selector: string): Promise<Glyph | null> {
  const block = blockOf(selector);
  if (!block) return null;
  return (await outlineShard(font, block))?.glyphs[selector] ?? null;
}

export function cutsShard(font: string, source: string, block: string): Promise<CutsFile | null> {
  return json<CutsFile>(cutsPath(font, source, block));
}

export const cutsShardOfSubject = (font: string, source: string, ref: string): Promise<CutsFile | null> => cutsShard(font, source, blockOfRef(ref));

export const forms = (chain: string): Promise<FormsFile | null> => json<FormsFile>(formsPath(chain));
export const library = (chain: string): Promise<LibraryFile | null> => json<LibraryFile>(libraryPath(chain));
export const cutsTable = (source: string): Promise<Table | null> => table(cutsTablePath(source));
export const skippedTable = (source: string): Promise<Table | null> => table(skippedTablePath(source));
export const componentsTable = (source: string): Promise<Table | null> => table(componentsTablePath(source));
export const releaseVerdicts = (): Promise<Table | null> => table("verdicts.tsv");

/** A glyph with the font that draws it. */
export interface Drawn {
  font: string;
  selector: string;
  glyph: Glyph;
}

/** The glyph a character is drawn from: the first font of the release, chains first, that has an outline for it. */
export async function drawn(rel: Release, selector: string): Promise<Drawn | null> {
  const order = [...new Set([...Object.values(rel.fonts.chains).flat(), ...rel.fonts.fonts.map((f) => f.id)])];
  for (const font of order) {
    const g = await glyph(font, selector);
    if (g) return { font, selector, glyph: g };
  }
  return null;
}

export interface ResolvedCut {
  cut: import("han-decompose").Cut;
  reading: import("han-decompose").Reading;
  glyph: Glyph | null;
  font: string;
  selector: string;
}

/** A cut by its identifier, with its reading and the glyph it was cut from. */
export function resolveCut(id: string): Promise<ResolvedCut | null> {
  const parts = parseCutId(id);
  if (!parts) return Promise.resolve(null);
  const key = `resolved:${id}`;
  let held = parsed.get(key) as Promise<ResolvedCut | null> | undefined;
  if (!held) {
    held = (async () => {
      const block = blockOf(parts.selector);
      if (!block) return null;
      const shard = await cutsShard(parts.font, parts.source, block);
      const glyphId = `${parts.font}/${parts.selector}`;
      const reading = shard?.readings.find((r) => r.glyph === glyphId && r.description === parts.description && r.cuts.some((c) => c.id === id));
      const cut = reading?.cuts.find((c) => c.id === id);
      if (!reading || !cut) return null;
      return { cut, reading, glyph: await glyph(parts.font, parts.selector), font: parts.font, selector: parts.selector };
    })();
    parsed.set(key, held);
  }
  return held;
}

/** Counts of a font under a source, with the missing ones as zero. */
export function countsOf(rel: Release, font: string, source: string): Required<Counts> {
  const c = rel.manifest.counts[font]?.[source] ?? {};
  return { readings: c.readings ?? 0, skipped: c.skipped ?? 0, components: c.components ?? 0, cuts: c.cuts ?? {} };
}

/** Every verdict known: the release's, and in development the repository's. */
export async function verdicts(): Promise<VerdictRow[]> {
  const rows = ((await releaseVerdicts())?.rows ?? []) as unknown as VerdictRow[];
  if (!import.meta.env.DEV) return rows;
  try {
    const response = await fetch("/api/verdicts");
    if (response.ok && (response.headers.get("content-type") ?? "").includes("json")) return [...rows, ...((await response.json()) as VerdictRow[])];
  } catch {
    /* no dev server: read-only */
  }
  return rows;
}

export async function postVerdict(row: Omit<VerdictRow, "at" | "reviewer">): Promise<VerdictRow> {
  const response = await fetch("/api/verdict", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(row) });
  if (!response.ok) throw new Error(`verdict refused: ${response.status}`);
  return (await response.json()) as VerdictRow;
}
