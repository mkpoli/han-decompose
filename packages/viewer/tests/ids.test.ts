import { expect, test } from "bun:test";
import { codePointId, componentRef, componentText, glyphSelector, needsOutline, parseCutId, parseSelector, pathText, selectorOfChar, selectorText } from "../src/lib/ids.ts";
import { search } from "../src/lib/search.ts";

test("code points are upper hex of at least four digits", () => {
  expect(codePointId(0x5ac)).toBe("U+05AC");
  expect(codePointId(0x20b36)).toBe("U+20B36");
});

test("selectors split into code point, variation selector and index", () => {
  expect(parseSelector("U+845B.E0100")).toEqual({ cp: 0x845b, vs: 0xe0100, gid: null });
  expect(parseSelector("gid.12")).toEqual({ cp: null, vs: null, gid: 12 });
  expect(parseSelector("U+845B.4E00")).toBeNull();
  expect(parseSelector("U+020B36")).toBeNull();
  expect(parseSelector("U+D800")).toBeNull();
  expect(parseSelector("U+110000")).toBeNull();
  expect(parseSelector("gid.012")).toBeNull();
});

test("a path value is put in its canonical spelling", () => {
  expect(glyphSelector("u+5d14")).toBe("U+5D14");
  expect(glyphSelector("U+845b.e0100")).toBe("U+845B.E0100");
  expect(glyphSelector("5D14")).toBeNull();
});

test("characters and selectors convert both ways", () => {
  expect(selectorOfChar("崔")).toBe("U+5D14");
  expect(selectorOfChar("𠀇")).toBe("U+20007");
  expect(selectorOfChar("葛\u{E0100}")).toBe("U+845B.E0100");
  expect(selectorOfChar("崔崔")).toBeNull();
  expect(selectorText("U+5D14")).toBe("崔");
});

test("the characters machines lack are the ones drawn from outlines", () => {
  expect(needsOutline(0x5d14)).toBe(false);
  expect(needsOutline(0x3400)).toBe(false);
  expect(needsOutline(0x20007)).toBe(true);
  expect(needsOutline(0xf2a5)).toBe(true);
});

test("notation becomes a component reference", () => {
  expect(componentRef("山")).toBe("u:5C71");
  expect(componentRef("u:5c71")).toBe("u:5C71");
  expect(componentRef("{42}")).toBe("bs:42");
  expect(componentRef("&CDP-8958;")).toBe("chise:CDP-8958");
  expect(componentRef("#(丿𠃊)")).toBe("zi:#(丿𠃊)");
  expect(componentRef("⿱𰀪亻")).toBe("ids:⿱𰀪亻");
  expect(componentRef("chise:CDP-8958")).toBe("chise:CDP-8958");
  expect(componentRef("abc")).toBeNull();
  expect(componentRef("")).toBeNull();
});

test("a reference is written as a description writes it", () => {
  expect(componentText("u:5C71")).toBe("山");
  expect(componentText("bs:42")).toBe("{42}");
  expect(componentText("chise:CDP-8958")).toBe("&CDP-8958;");
  expect(componentText("zi:#(丿𠃊)")).toBe("#(丿𠃊)");
});

test("a cut identifier splits into glyph, description and path", () => {
  expect(parseCutId("noto-sans-cjk-jp@2.004/U+5019~chise.74d9fdff~1.1")).toEqual({
    font: "noto-sans-cjk-jp@2.004",
    selector: "U+5019",
    description: "chise.74d9fdff",
    source: "chise",
    path: "1.1",
  });
  expect(parseCutId("ids-input-components.12345678".replace(/^/, "f@1/U+4E00~") + "~-")?.source).toBe("ids-input-components");
  expect(parseCutId("nonsense")).toBeNull();
});

test("a path is dotted, and the root is a hyphen", () => {
  expect(pathText([])).toBe("-");
  expect(pathText([1, 0])).toBe("1.0");
});

test("search leads a character to its page and a component to its own", () => {
  const ctx = { fonts: [{ id: "noto-sans-cjk-jp@2.004", name: "Noto Sans CJK JP" }] as never, components: new Set(["u:5C71"]) };
  expect(search("崔", ctx)).toEqual([{ kind: "char", id: "U+5D14", text: "崔" }]);
  expect(search("u+5c71", ctx).map((h) => h.kind)).toEqual(["char", "component"]);
  expect(search("{42}", ctx)).toEqual([{ kind: "component", ref: "bs:42", text: "{42}" }]);
  expect(search("noto sans", ctx)).toEqual([{ kind: "font", id: "noto-sans-cjk-jp@2.004", name: "Noto Sans CJK JP" }]);
  expect(search("  ", ctx)).toEqual([]);
});
