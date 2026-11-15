// The colour theme: the system's, or light or dark whatever it says. It is kept per viewer and set
// on the root as data-theme before the page paints (the script in index.html).
import { load, save } from "./storage.ts";

export type Theme = "system" | "light" | "dark";
export const THEMES: Theme[] = ["system", "light", "dark"];

export function storedTheme(): Theme {
  const theme = load<Theme>("theme", "system");
  return THEMES.includes(theme) ? theme : "system";
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  save("theme", theme === "system" ? undefined : theme);
}
