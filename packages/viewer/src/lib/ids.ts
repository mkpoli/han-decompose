/** Identifiers of docs/format.md section 2: code points, selectors, components and cuts. */

/** U+FE00–U+FE0F and U+E0100–U+E01EF. */
const VARIATION = /^(?:FE0[0-9A-F]|E01[0-9A-E][0-9A-F])$/;

/** `U+50AC` for a code point: upper-case hex of at least four digits. */
export function codePointId(cp: number): string {
  return `U+${cp.toString(16).toUpperCase().padStart(4, "0")}`;
}

export interface Selector {
  /** The glyph's code point, or null for a glyph selected by index. */
  cp: number | null;
  /** The variation selector's code point, for a variation sequence. */
  vs: number | null;
  gid: number | null;
}

/** Splits a glyph selector (`U+845B.E0100`, `gid.1234`); null for any other text. */
export function parseSelector(text: string): Selector | null {
  const gid = /^gid\.(0|[1-9][0-9]*)$/.exec(text);
  if (gid) return { cp: null, vs: null, gid: Number(gid[1]) };
  const match = /^U\+([0-9A-F]{4,6})(?:\.([0-9A-F]{4,5}))?$/.exec(text);
  if (!match) return null;
  const cp = parseInt(match[1] ?? "", 16);
  if (cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) return null;
  if ((match[1] ?? "").length > 4 && (match[1] ?? "").startsWith("0")) return null;
  let vs: number | null = null;
  if (match[2] !== undefined) {
    if (!VARIATION.test(match[2])) return null;
    vs = parseInt(match[2], 16);
  }
  return { cp, vs, gid: null };
}

/** The canonical selector for a path value, accepting lower case; null when it names no glyph. */
export function glyphSelector(text: string): string | null {
  const upper = text.replace(/^u\+/i, "U+").replace(/^U\+([0-9a-f]+)(?:\.([0-9a-f]+))?$/i, (_, a: string, b?: string) => `U+${a.toUpperCase()}${b ? `.${b.toUpperCase()}` : ""}`);
  return parseSelector(upper) ? upper : null;
}

/** The text a selector stands for: the character, with its variation selector. */
export function selectorText(selector: string): string {
  const parsed = parseSelector(selector);
  if (!parsed || parsed.cp === null) return "";
  return String.fromCodePoint(parsed.cp) + (parsed.vs === null ? "" : String.fromCodePoint(parsed.vs));
}

/** The selector of one character text, or null when it is not a single character. */
export function selectorOfChar(text: string): string | null {
  const points = [...text];
  if (points.length === 1) return codePointId(points[0]!.codePointAt(0)!);
  if (points.length === 2) {
    const vs = points[1]!.codePointAt(0)!;
    const hex = vs.toString(16).toUpperCase();
    if (VARIATION.test(hex)) return `${codePointId(points[0]!.codePointAt(0)!)}.${hex}`;
  }
  return null;
}

/** Whether a code point is one that most machines cannot draw: Extension B and later, the private use areas. */
export function needsOutline(cp: number): boolean {
  return cp >= 0x20000 || (cp >= 0xe000 && cp <= 0xf8ff) || cp >= 0xf0000;
}

const IDC = /[⿰-⿿㇯〾]/u;

/** The component reference a piece of notation names, or null (docs/format.md 2.4). */
export function componentRef(text: string): string | null {
  const t = text.trim();
  if (!t) return null;
  const explicit = /^(u|bs|chise|aj1|zi|ids):(.+)$/s.exec(t);
  if (explicit) {
    const [, kind, value] = explicit as unknown as [string, string, string];
    if (kind === "u") {
      const sel = glyphSelector(`U+${value}`);
      return sel ? `u:${sel.slice(2)}` : null;
    }
    return `${kind}:${value}`;
  }
  const bs = /^\{(\d+)\}$/.exec(t);
  if (bs) return `bs:${bs[1]}`;
  const chise = /^&(.+);$/.exec(t);
  if (chise) return `chise:${chise[1]}`;
  if (t.startsWith("#(")) return `zi:${t}`;
  if (IDC.test(t[0] ?? "")) return `ids:${t}`;
  const sel = selectorOfChar(t);
  return sel ? `u:${sel.slice(2)}` : null;
}

/** The text a component reference is written as in a description. */
export function componentText(ref: string): string {
  const i = ref.indexOf(":");
  const kind = ref.slice(0, i);
  const value = ref.slice(i + 1);
  switch (kind) {
    case "u": {
      const [hex = "", vs] = value.split(".");
      return String.fromCodePoint(parseInt(hex, 16)) + (vs ? String.fromCodePoint(parseInt(vs, 16)) : "");
    }
    case "bs":
      return `{${value}}`;
    case "chise":
      return `&${value};`;
    case "aj1":
      return `aj1:${value}`;
    default:
      return value;
  }
}

/** The glyph selector a `u:` reference names, or null for other kinds. */
export function refSelector(ref: string): string | null {
  return ref.startsWith("u:") ? `U+${ref.slice(2)}` : null;
}

/** The reference of a character's selector; null for a glyph selected by index, which no component names. */
export function selectorRef(selector: string): string | null {
  return selector.startsWith("U+") ? `u:${selector.slice(2)}` : null;
}

const SLUG = "[a-z0-9]+(?:-[a-z0-9]+)*";
const CUT_ID = new RegExp(`^(${SLUG}@[A-Za-z0-9]+(?:\\.[A-Za-z0-9]+)*)/([^~/]+)~(${SLUG}\\.[0-9a-f]{8})~(-|(?:0|[1-9][0-9]*)(?:\\.(?:0|[1-9][0-9]*))*)$`);

/** Whether a text is a cut identifier of docs/format.md 2.6, down to the selector. */
export function isCutId(text: string): boolean {
  const match = CUT_ID.exec(text);
  return match !== null && parseSelector(match[2] ?? "") !== null;
}

export interface CutId {
  font: string;
  selector: string;
  description: string;
  source: string;
  path: string;
}

/** Splits `<font>/<selector>~<description>~<path>`. */
export function parseCutId(id: string): CutId | null {
  const parts = id.split("~");
  if (parts.length !== 3) return null;
  const [glyph = "", description = "", path = ""] = parts;
  const slash = glyph.indexOf("/");
  const dot = description.lastIndexOf(".");
  if (slash < 0 || dot < 0) return null;
  return { font: glyph.slice(0, slash), selector: glyph.slice(slash + 1), description, source: description.slice(0, dot), path };
}

/** A path as text: `-` for the root, else the indices joined by dots (2.5). */
export function pathText(path: number[]): string {
  return path.length ? path.join(".") : "-";
}
