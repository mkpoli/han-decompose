// Per-viewer settings in localStorage, under `han-decompose:<name>`. Every read and write may fail
// (a private window, storage blocked); the page then runs on its defaults.

export function load<T>(name: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`han-decompose:${name}`);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function save(name: string, value: unknown): void {
  try {
    if (value === undefined) localStorage.removeItem(`han-decompose:${name}`);
    else localStorage.setItem(`han-decompose:${name}`, JSON.stringify(value));
  } catch {
    /* Storage unavailable: the setting lasts for this visit. */
  }
}
