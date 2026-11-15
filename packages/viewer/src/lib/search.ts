/** The search field of the home page: what a piece of text names. */
import type { FontEntry } from "han-decompose";
import { componentRef, componentText, parseSelector, selectorOfChar, selectorText } from "./ids.ts";

export type Hit =
  | { kind: "char"; id: string; text: string }
  | { kind: "component"; ref: string; text: string }
  | { kind: "font"; id: string; name: string };

export interface SearchContext {
  fonts: FontEntry[];
  /** References of the components the release has forms or library cuts for. */
  components: ReadonlySet<string>;
}

/** The pages a query leads to, best first. */
export function search(query: string, ctx: SearchContext): Hit[] {
  const q = query.trim();
  if (!q) return [];
  const hits: Hit[] = [];
  const seen = new Set<string>();
  const add = (hit: Hit): void => {
    const key = hit.kind === "char" ? `c${hit.id}` : hit.kind === "component" ? `k${hit.ref}` : `f${hit.id}`;
    if (!seen.has(key)) {
      seen.add(key);
      hits.push(hit);
    }
  };
  const upper = q.toUpperCase().replace(/^U\+?/, "U+");
  const selector = parseSelector(upper) ? upper : selectorOfChar(q);
  if (selector) {
    add({ kind: "char", id: selector, text: selectorText(selector) });
    const ref = `u:${selector.slice(2)}`;
    if (ctx.components.has(ref)) add({ kind: "component", ref, text: componentText(ref) });
  }
  const ref = componentRef(q);
  if (ref && !selector) add({ kind: "component", ref, text: componentText(ref) });
  else if (ref && !ref.startsWith("u:")) add({ kind: "component", ref, text: componentText(ref) });
  const needle = q.toLowerCase();
  for (const font of ctx.fonts) {
    if (font.id.toLowerCase().includes(needle) || font.name.toLowerCase().includes(needle)) add({ kind: "font", id: font.id, name: font.name });
  }
  return hits;
}
