/** What a release holds for one glyph selector: per font, its outline and, per source, its readings and skipped attempts. */
import type { FontEntry, Glyph, Reading, Skipped } from "han-decompose";
import { blockOf } from "./addressing.ts";
import { chainFonts, cutsShard, glyph, sourcesOfFont, type Release } from "./data.ts";
import { selectorRef } from "./ids.ts";

export interface SourceCell {
  source: string;
  readings: Reading[];
  skipped: Skipped[];
}

export interface FontRow {
  font: FontEntry;
  chain: string;
  glyph: Glyph | null;
  cells: SourceCell[];
}

export async function charRows(rel: Release, selector: string, only?: string): Promise<FontRow[]> {
  const block = blockOf(selector);
  if (!block) return [];
  const ref = selectorRef(selector);
  const rows = await Promise.all(
    chainFonts(rel).flatMap(({ chain, fonts }) =>
      fonts.filter((font) => only === undefined || font.id === only).map(async (font): Promise<FontRow> => {
        const here = `${font.id}/${selector}`;
        const [g, cells] = await Promise.all([
          glyph(font.id, selector),
          Promise.all(
            sourcesOfFont(rel, font.id).map(async (source): Promise<SourceCell> => {
              const shard = await cutsShard(font.id, source, block);
              return {
                source,
                readings: shard?.readings.filter((r) => r.glyph === here) ?? [],
                skipped: shard?.skipped.filter((s) => s.glyph === here || (s.glyph === undefined && ref !== null && s.subject === ref)) ?? [],
              };
            }),
          ),
        ]);
        return { font, chain, glyph: g, cells };
      }),
    ),
  );
  return rows.filter((row) => row.glyph || row.cells.some((c) => c.readings.length || c.skipped.length));
}
