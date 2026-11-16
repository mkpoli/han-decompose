/**
 * GlyphWiki's `dump_newest_only.txt` is a psql table: ` name | related | data`, padded,
 * with a header, a rule and a localised row count that are skipped here.
 */
export function parseDumpLine(line: string): [name: string, data: string] | null {
  const i = line.indexOf("|");
  if (i < 0) return null;
  const j = line.indexOf("|", i + 1);
  if (j < 0) return null;
  const name = line.slice(0, i).trim();
  if (name === "" || name === "name" || name.startsWith("---")) return null;
  return [name, line.slice(j + 1).trim()];
}

/** Reads dump files into name → KAGE data; `related` is not read. Later files add to earlier ones. */
export async function readDump(...paths: string[]): Promise<Map<string, string>> {
  const glyphs = new Map<string, string>();
  for (const path of paths) await readInto(glyphs, path);
  return glyphs;
}

async function readInto(glyphs: Map<string, string>, path: string): Promise<void> {
  const decoder = new TextDecoder();
  let rest = "";
  const take = (line: string) => {
    const row = parseDumpLine(line);
    if (row) glyphs.set(row[0], row[1]);
  };
  for await (const chunk of Bun.file(path).stream()) {
    const lines = (rest + decoder.decode(chunk, { stream: true })).split("\n");
    rest = lines.pop() ?? "";
    for (const line of lines) take(line);
  }
  take(rest + decoder.decode());
}
