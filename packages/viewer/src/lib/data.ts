/** The one module that fetches a release: files, caching and shard addressing. */
import type { Counts, CutsFile, FontEntry, FontsFile, FormsFile, Glyph, LibraryFile, Manifest, OutlineFile, SourceEntry, SourcesFile, VerdictRow } from "han-decompose";
import { blockOf, blockOfRef, componentsTablePath, cutsPath, cutsTablePath, formsPath, libraryPath, outlinePath, skippedTablePath, urlPath } from "./addressing.ts";
import { gunzipIfNeeded, streamLines } from "./codec.ts";
import { BoundedHeap } from "./heap.ts";
import { Lru } from "./lru.ts";
import { parseCutId } from "./ids.ts";
import { parseTable, type Table } from "./tsv.ts";

const BASE = `${import.meta.env.BASE_URL}data/`;

/** The address of a file of the release. */
export const dataUrl = (path: string): string => BASE + urlPath(path);

const decoder = new TextDecoder();

let listing: Promise<Set<string>> | null = null;

/** The paths the manifest lists: a file it does not list is not asked for. */
function listed(): Promise<Set<string>> {
  listing ??= (async () => {
    const response = await fetch(dataUrl("manifest.json"));
    if (!response.ok) throw new Error("no manifest");
    const manifest = (await response.json()) as Manifest;
    return new Set<string>([...manifest.files.map((f) => f.path), "fonts.json", "sources.json"]);
  })().catch((error: unknown) => {
    listing = null;
    throw error;
  });
  return listing;
}

/** Whether a file is in the release; a missing release says no. */
async function has(path: string): Promise<boolean> {
  if (path === "manifest.json") return true;
  try {
    return (await listed()).has(path);
  } catch {
    return false;
  }
}

/** The response for a file of the release, or null where it is not there. A host that answers a miss with the app is a miss. */
async function open(path: string): Promise<Response | null> {
  try {
    if (!(await has(path))) return null;
    const response = await fetch(dataUrl(path));
    if (!response.ok || (response.headers.get("content-type") ?? "").includes("text/html")) return null;
    return response;
  } catch {
    return null;
  }
}

/** Parsed files, the most recently used 64 of them. Bytes are not kept; a failure is not kept either. */
const parsed = new Lru<string, Promise<unknown>>(64);

function cached<T>(path: string, read: (data: Uint8Array) => T): Promise<T | null> {
  let held = parsed.get(path) as Promise<T | null> | undefined;
  if (!held) {
    held = (async () => {
      const response = await open(path);
      if (!response) return null;
      return read(await gunzipIfNeeded(new Uint8Array(await response.arrayBuffer())));
    })().then(
      (value) => {
        if (value === null) parsed.delete(path);
        return value;
      },
      (error: unknown) => {
        parsed.delete(path);
        throw error;
      },
    );
    parsed.set(path, held);
  }
  return held;
}

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
  })().catch((error: unknown) => {
    releasePromise = null;
    throw error;
  });
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
export async function resolveCut(id: string): Promise<ResolvedCut | null> {
  const parts = parseCutId(id);
  if (!parts) return null;
  const block = blockOf(parts.selector);
  if (!block) return null;
  const shard = await cutsShard(parts.font, parts.source, block);
  const glyphId = `${parts.font}/${parts.selector}`;
  const reading = shard?.readings.find((r) => r.glyph === glyphId && r.description === parts.description && r.cuts.some((c) => c.id === id));
  const cut = reading?.cuts.find((c) => c.id === id);
  if (!reading || !cut) return null;
  return { cut, reading, glyph: await glyph(parts.font, parts.selector), font: parts.font, selector: parts.selector };
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

/** The columns of `cuts.<source>.tsv.gz` the review page uses. */
export interface QueueRow {
  cut_id: string;
  sig: string;
  font: string;
  source: string;
  method: string;
  status: string;
  component: string;
  fit: string;
}

const KEPT_COLUMNS: (keyof QueueRow)[] = ["cut_id", "sig", "font", "source", "method", "status", "component", "fit"];

/** The cut tables the release has, by source. */
export const cutTableSources = async (rel: Release): Promise<string[]> => {
  const paths = await listed().catch(() => new Set<string>());
  return rel.sources.sources.map((s) => s.id).filter((id) => paths.has(cutsTablePath(id)));
};

const queues = new Lru<string, Promise<QueueRow[]>>(6);

/**
 * The `limit` weakest cuts of a source with one of the statuses, weakest first. The table is read
 * line by line and only these columns of the rows kept are held, so a large release never sits whole in memory.
 */
export function weakestCuts(source: string, statuses: readonly string[], limit = 2000): Promise<QueueRow[]> {
  const key = `${source}|${statuses.join(",")}|${limit}`;
  let held = queues.get(key);
  if (!held) {
    held = (async () => {
      const response = await open(cutsTablePath(source));
      if (!response?.body) return [];
      const heap = new BoundedHeap<QueueRow>(limit, (row) => (row.fit === "" ? Number.POSITIVE_INFINITY : Number(row.fit)));
      let at: number[] | null = null;
      for await (const line of streamLines(response.body)) {
        if (!line) continue;
        if (at === null) {
          if (line.startsWith("#")) continue;
          const names = line.split("\t");
          at = KEPT_COLUMNS.map((name) => names.indexOf(name));
          continue;
        }
        const cells = line.split("\t");
        const row = {} as QueueRow;
        KEPT_COLUMNS.forEach((name, i) => {
          row[name] = cells[at![i] ?? -1] ?? "";
        });
        if (statuses.includes(row.status)) heap.push(row);
      }
      return heap.sorted().sort((a, b) => Number(a.fit === "" ? Infinity : a.fit) - Number(b.fit === "" ? Infinity : b.fit) || a.cut_id.localeCompare(b.cut_id));
    })().catch((error: unknown) => {
      queues.delete(key);
      throw error;
    });
    queues.set(key, held);
  }
  return held;
}
