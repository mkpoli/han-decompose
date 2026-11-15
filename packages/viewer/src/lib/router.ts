/** Paths of the viewer and the routes they name. */
import { glyphSelector } from "./ids.ts";

export type Route =
  | { name: "home" }
  | { name: "char"; id: string }
  | { name: "component"; ref: string }
  | { name: "font"; id: string }
  | { name: "skipped" }
  | { name: "review" }
  | { name: "missing"; path: string };

/** Characters of a path segment that stay readable: the identifiers use them freely. */
const KEPT = /%(?:3A|40|2B|23|28|29)/gi;
const KEPT_CHAR: Record<string, string> = { "%3A": ":", "%40": "@", "%2B": "+", "%23": "#", "%28": "(", "%29": ")" };

const segment = (text: string): string => encodeURIComponent(text).replace(KEPT, (m) => KEPT_CHAR[m.toUpperCase()] ?? m);

export function routeHref(route: Route): string {
  switch (route.name) {
    case "home":
      return "/";
    case "char":
      return `/char/${segment(route.id)}`;
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
  const match = /^\/(char|component|font)\/(.+)$/.exec(path);
  if (match) {
    const value = decode(match[2] ?? "");
    if (value) {
      if (match[1] === "char") {
        const id = glyphSelector(value);
        if (id) return { name: "char", id };
      } else if (match[1] === "component") return { name: "component", ref: value };
      else return { name: "font", id: value };
    }
  }
  return { name: "missing", path };
}
