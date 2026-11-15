/** What a release says about components: relations, which components have forms, and reference glyphs. */
import { chainFonts, componentsTable, drawn, forms, glyph, library, type Drawn, type Release } from "./data.ts";
import { refSelector } from "./ids.ts";

export interface Relation {
  component: string;
  kind: string;
  text: string;
  relation: string;
  target: string;
  basis: string;
  tier: string;
  source: string;
}

const relationIndexes = new Map<Release, Promise<Map<string, Relation[]>>>();

/** Every relation, filed under both of its components. */
export function relationIndex(rel: Release): Promise<Map<string, Relation[]>> {
  let held = relationIndexes.get(rel);
  if (!held) {
    held = (async () => {
      const index = new Map<string, Relation[]>();
      const tables = await Promise.all(rel.sources.sources.map((s) => componentsTable(s.id)));
      for (const t of tables) {
        for (const row of (t?.rows ?? []) as unknown as Relation[]) {
          if (!row.relation) continue;
          for (const key of new Set([row.component, row.target])) index.set(key, [...(index.get(key) ?? []), row]);
        }
      }
      return index;
    })();
    relationIndexes.set(rel, held);
  }
  return held;
}

const known = new Map<Release, Promise<Set<string>>>();

/** The references of the components that have a form or library cuts in any chain. */
export function knownComponents(rel: Release): Promise<Set<string>> {
  let held = known.get(rel);
  if (!held) {
    held = (async () => {
      const set = new Set<string>();
      for (const { chain } of chainFonts(rel)) {
        const [f, l] = await Promise.all([forms(chain), library(chain)]);
        for (const ref of Object.keys(f?.forms ?? {})) set.add(ref);
        for (const ref of Object.keys(l?.library ?? {})) set.add(ref);
      }
      return set;
    })();
    known.set(rel, held);
  }
  return held;
}

/** The glyph that stands for a component: its own outline for a character, the reference font's for a component a source numbers. */
export async function referenceGlyph(rel: Release, ref: string): Promise<Drawn | null> {
  const own = refSelector(ref);
  if (own) {
    const found = await drawn(rel, own);
    if (found) return found;
  }
  const chained = new Set(Object.values(rel.fonts.chains).flat());
  const outside = rel.fonts.fonts.filter((f) => !chained.has(f.id));
  const relations = (await relationIndex(rel)).get(ref) ?? [];
  for (const r of relations) {
    const other = r.component === ref ? r.target : r.component;
    const selector = refSelector(other);
    if (!selector) continue;
    for (const font of outside) {
      const g = await glyph(font.id, selector);
      if (g) return { font: font.id, selector, glyph: g };
    }
  }
  return null;
}
