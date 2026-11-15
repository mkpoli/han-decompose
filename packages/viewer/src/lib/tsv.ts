/** Tables of docs/format.md section 5. */

export interface Table {
  /** The first line, `# format=… release=…`. */
  meta: string;
  columns: string[];
  rows: Record<string, string>[];
}

export function parseTable(text: string): Table {
  const lines = text.split("\n");
  let meta = "";
  let columns: string[] | null = null;
  const rows: Record<string, string>[] = [];
  for (const line of lines) {
    if (line === "") continue;
    if (columns === null) {
      if (line.startsWith("#")) {
        meta = line;
        continue;
      }
      columns = line.split("\t");
      continue;
    }
    const cells = line.split("\t");
    const row: Record<string, string> = {};
    columns.forEach((name, i) => {
      row[name] = cells[i] ?? "";
    });
    rows.push(row);
  }
  return { meta, columns: columns ?? [], rows };
}

/** The release name a table's first line states. */
export function tableRelease(meta: string): string {
  return /release=(\S+)/.exec(meta)?.[1] ?? "";
}

/** A cell with the characters a table cannot hold replaced by a space. */
export const cell = (value: string): string => value.replace(/[\u0000-\u001f\u007f]/g, " ").trim();
