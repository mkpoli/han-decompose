/** Where a release keeps what (docs/format.md section 4). */
import { parseSelector } from "./ids.ts";

/** The shard of a glyph: its code point divided by 256 in lower-case hex of at least three digits; `gid` for an index. */
export function blockOf(selector: string): string | null {
  const parsed = parseSelector(selector);
  if (!parsed) return null;
  if (parsed.cp === null) return "gid";
  return (parsed.cp >> 8).toString(16).padStart(3, "0");
}

/** The block of a subject's code point, `gid` for a subject that is no character. */
export function blockOfRef(ref: string): string {
  if (!ref.startsWith("u:")) return "gid";
  return blockOf(`U+${ref.slice(2)}`) ?? "gid";
}

export const outlinePath = (font: string, block: string): string => `outlines/${font}/${block}.json.gz`;
export const cutsPath = (font: string, source: string, block: string): string => `cuts/${font}/${source}/${block}.json.gz`;
export const formsPath = (chain: string): string => `forms/${chain}.json.gz`;
export const libraryPath = (chain: string): string => `library/${chain}.json.gz`;
export const cutsTablePath = (source: string): string => `cuts.${source}.tsv.gz`;
export const skippedTablePath = (source: string): string => `skipped.${source}.tsv.gz`;
export const componentsTablePath = (source: string): string => `components.${source}.tsv`;

/** A release path as a URL path: each segment percent-encoded, so `@` in a font identifier reaches
 *  the host as `%40`, the spelling it serves without a redirect. */
export const urlPath = (path: string): string => path.split("/").map(encodeURIComponent).join("/");
