// The interface languages: JSON catalogues in src/locales, English filling any key a catalogue lacks.
import en from "../locales/en.json";
import ja from "../locales/ja.json";
import { load, save } from "./storage.ts";

export type Key = keyof typeof en;
export const LOCALES = [
  ["en", "English"],
  ["ja", "日本語"],
] as const;
export type Locale = (typeof LOCALES)[number][0];

const catalogues: Record<Locale, Partial<Record<Key, string>>> = { en, ja };

function initial(): Locale {
  const stored = load<string>("locale", "");
  if (stored === "en" || stored === "ja") return stored;
  return navigator.language.toLowerCase().startsWith("ja") ? "ja" : "en";
}

const state = $state({ locale: initial() });

export const locale = (): Locale => state.locale;

export function setLocale(next: Locale): void {
  state.locale = next;
  document.documentElement.lang = next;
  save("locale", next);
}

/** The text of a key in the current language; `{name}` takes its value from `params`. */
export function t(key: Key, params?: Record<string, string | number>): string {
  const text = catalogues[state.locale][key] ?? en[key];
  return params ? text.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`)) : text;
}

/** A number written for the current language. */
export const n = (value: number): string => value.toLocaleString(state.locale);

/** A key built at run time, as the name of a status or a relation; the name itself where the catalogue has none. */
export function tx(key: string): string {
  return catalogues[state.locale][key as Key] ?? en[key as Key] ?? key.slice(key.indexOf(".") + 1);
}
