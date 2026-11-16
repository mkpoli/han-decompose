/** The verdict table of the repository: validating a verdict and writing its row (docs/format.md 5.4). */
import type { VerdictRow } from "../src/lib/format1";
import { isCutId } from "../src/lib/ids.ts";
import { cell } from "../src/lib/tsv.ts";

export const VERDICT_COLUMNS = ["cut_id", "sig", "verdict", "note", "reviewer", "at", "release"] as const;

export const VERDICT_HEADER = `# format=han-decompose/verdicts-tsv@1.0\n${VERDICT_COLUMNS.join("\t")}\n`;

export type VerdictInput = Pick<VerdictRow, "cut_id" | "sig" | "verdict" | "note" | "release">;

/** The input a request carries, or the reason it is refused. */
export function readVerdict(body: unknown): { ok: true; value: VerdictInput } | { ok: false; error: string } {
  if (typeof body !== "object" || body === null) return { ok: false, error: "body is not an object" };
  const b = body as Record<string, unknown>;
  const text = (key: string): string => (typeof b[key] === "string" ? (b[key] as string) : "");
  const cut_id = text("cut_id");
  if (!isCutId(cut_id)) return { ok: false, error: "cut_id is not a cut identifier" };
  const sig = text("sig");
  if (!/^[0-9a-f]{8}$/.test(sig)) return { ok: false, error: "sig is not eight hex digits" };
  const verdict = text("verdict");
  if (verdict !== "right" && verdict !== "wrong") return { ok: false, error: "verdict is right or wrong" };
  const release = text("release");
  if (!/^[A-Za-z0-9._+-]*$/.test(release)) return { ok: false, error: "release name has a character it may not hold" };
  return { ok: true, value: { cut_id, sig, verdict, note: cell(text("note")), release } };
}

/** `YYYY-MM-DDThh:mm:ssZ`. */
export const stamp = (date: Date): string => date.toISOString().replace(/\.\d{3}Z$/, "Z");

export function verdictLine(row: VerdictRow): string {
  return `${VERDICT_COLUMNS.map((column) => cell(row[column])).join("\t")}\n`;
}

/** Whether a request may write a verdict: JSON from a page of this server. */
export function allowedRequest(headers: { "content-type"?: string | undefined; origin?: string | undefined; host?: string | undefined }): boolean {
  if (!(headers["content-type"] ?? "").toLowerCase().startsWith("application/json")) return false;
  const { origin, host } = headers;
  if (!origin || !host) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}
