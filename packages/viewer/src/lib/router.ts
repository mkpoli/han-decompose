/** Paths of the viewer and the routes they name. */
import { glyphSelector } from "./ids.ts";

export type Route =
  | { name: "home" }
  /** `font` is set for a glyph selected by index, which only one font has. */
  | { name: "char"; id: string; font?: string }
  | { name: "component"; ref: string }
  | { name: "font"; id: string }
  | { name: "skipped" }
  | { name: "review" }
  | { name: "missing"; path: string };

/** Characters of a path segment that stay readable: the identifiers use them freely. `#` and `?` stay encoded. */
const KEPT = /%(?:3A|40|2B|28|29)/gi;
const KEPT_CHAR: Record<string, string> = { "%3A": ":", "%40": "@", "%2B": "+", "%28": "(", "%29": ")" };

const segment = (text: string): string => encodeURIComponent(text).replace(KEPT, (m) => KEPT_CHAR[m.toUpperCase()] ?? m);

export function routeHref(route: Route): string {
  switch (route.name) {
    case "home":
      return "/";
    case "char":
      return route.font ? `/char/${segment(route.font)}/${segment(route.id)}` : `/char/${segment(route.id)}`;
    case "component":
      return `/component/${segment(route.ref)}`;
    case "font":
      return `/font/${segment(route.id)}`;
    case "skipped":
      return "/skipped";
    case "review":
      return "/review";
    case "missing":
      return route.path;
  }
}

function decode(text: string): string | null {
  try {
    return decodeURIComponent(text);
  } catch {
    return null;
  }
}

export function parseRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/") return { name: "home" };
  if (path === "/skipped") return { name: "skipped" };
  if (path === "/review") return { name: "review" };
  const index = /^\/char\/([^/]+)\/([^/]+)$/.exec(path);
  if (index) {
    const font = decode(index[1] ?? "");
    const id = decode(index[2] ?? "");
    if (font && id && /^gid\.(0|[1-9][0-9]*)$/.test(id)) return { name: "char", id, font };
    return { name: "missing", path };
  }
  const match = /^\/(char|component|font)\/(.+)$/.exec(path);
  if (match) {
    const value = decode(match[2] ?? "");
    if (value) {
      if (match[1] === "char") {
        const id = glyphSelector(value);
        if (id && !id.startsWith("gid.")) return { name: "char", id };
      } else if (match[1] === "component") return { name: "component", ref: value };
      else return { name: "font", id: value };
    }
  }
  return { name: "missing", path };
}

/** The route of a glyph: a glyph selected by index belongs to its font. */
export const charRoute = (selector: string, font: string): Route => (selector.startsWith("gid.") ? { name: "char", id: selector, font } : { name: "char", id: selector });

export const charHref = (selector: string, font: string): string => routeHref(charRoute(selector, font));
