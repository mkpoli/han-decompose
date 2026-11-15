import { expect, test } from "bun:test";
import { parseRoute, routeHref, type Route } from "../src/lib/router.ts";

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
