import { expect, test } from "bun:test";
import { charHref, parseRoute, routeHref, type Route } from "../src/lib/router.ts";

test("every route has a path", () => {
  expect(parseRoute("/")).toEqual({ name: "home" });
  expect(parseRoute("/char/U+5D14")).toEqual({ name: "char", id: "U+5D14" });
  expect(parseRoute("/char/u+5d14")).toEqual({ name: "char", id: "U+5D14" });
  expect(parseRoute("/component/u:5C71")).toEqual({ name: "component", ref: "u:5C71" });
  expect(parseRoute("/font/noto-sans-cjk-jp@2.004")).toEqual({ name: "font", id: "noto-sans-cjk-jp@2.004" });
  expect(parseRoute("/skipped")).toEqual({ name: "skipped" });
  expect(parseRoute("/review/")).toEqual({ name: "review" });
});

test("a component reference is URL-encoded", () => {
  expect(parseRoute("/component/ids:%E2%BF%B1%F0%B0%80%AA%E4%BA%BB")).toEqual({ name: "component", ref: "ids:⿱𰀪亻" });
  expect(parseRoute("/component/zi:%23(%E4%B8%BF)")).toEqual({ name: "component", ref: "zi:#(丿)" });
  expect(parseRoute("/component/chise:CDP-8958")).toEqual({ name: "component", ref: "chise:CDP-8958" });
});

test("paths and routes round trip", () => {
  const routes: Route[] = [
    { name: "home" },
    { name: "char", id: "U+845B.E0100" },
    { name: "component", ref: "zi:#(丿𠃊)" },
    { name: "component", ref: "bs:42" },
    { name: "font", id: "jigmo2@20250912" },
    { name: "skipped" },
    { name: "review" },
  ];
  for (const route of routes) expect(parseRoute(routeHref(route))).toEqual(route);
  expect(routeHref({ name: "char", id: "U+5D14" })).toBe("/char/U+5D14");
  expect(routeHref({ name: "component", ref: "u:5C71" })).toBe("/component/u:5C71");
});

test("an unknown path is missing", () => {
  expect(parseRoute("/nowhere")).toEqual({ name: "missing", path: "/nowhere" });
  expect(parseRoute("/char/zzz")).toEqual({ name: "missing", path: "/char/zzz" });
  expect(parseRoute("/char/%E0%A4%A")).toEqual({ name: "missing", path: "/char/%E0%A4%A" });
});

test("a reference with a hash survives a real URL", () => {
  const route: Route = { name: "component", ref: "zi:#(丿𠃊)" };
  const href = routeHref(route);
  expect(href).not.toContain("#");
  expect(parseRoute(new URL(href, "https://example.org").pathname)).toEqual(route);
});

test("a glyph selected by index is addressed with its font", () => {
  expect(charHref("gid.12", "noto-sans-cjk-jp@2.004")).toBe("/char/noto-sans-cjk-jp@2.004/gid.12");
  expect(parseRoute("/char/noto-sans-cjk-jp@2.004/gid.12")).toEqual({ name: "char", id: "gid.12", font: "noto-sans-cjk-jp@2.004" });
  expect(charHref("U+5D14", "jigmo2@20250912")).toBe("/char/U+5D14");
  expect(parseRoute("/char/gid.12")).toEqual({ name: "missing", path: "/char/gid.12" });
  expect(parseRoute("/char/jigmo2@20250912/U+5D14")).toEqual({ name: "missing", path: "/char/jigmo2@20250912/U+5D14" });
});
