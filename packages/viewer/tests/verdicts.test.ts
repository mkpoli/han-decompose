import { expect, test } from "bun:test";
import { readVerdict, stamp, VERDICT_HEADER, verdictLine } from "../server/verdicts.ts";

const good = { cut_id: "noto-sans-cjk-jp@2.004/U+5019~chise.74d9fdff~1.1", sig: "4991a647", verdict: "right", note: "ok", release: "v0.0.0-trial" };

test("the file starts with its format line and the columns of 5.4", () => {
  expect(VERDICT_HEADER).toBe("# format=han-decompose/verdicts-tsv@1.0\ncut_id\tsig\tverdict\tnote\treviewer\tat\trelease\n");
});

test("a verdict is checked before it is written", () => {
  expect(readVerdict(good)).toEqual({ ok: true, value: good });
  expect(readVerdict({ ...good, verdict: "maybe" }).ok).toBe(false);
  expect(readVerdict({ ...good, sig: "XYZ" }).ok).toBe(false);
  expect(readVerdict({ ...good, cut_id: "nope" }).ok).toBe(false);
  expect(readVerdict({ ...good, release: "a b" }).ok).toBe(false);
  expect(readVerdict(null).ok).toBe(false);
});

test("a note holds no tab or line break", () => {
  const r = readVerdict({ ...good, note: "a\tb\nc" });
  expect(r.ok && r.value.note).toBe("a b c");
});

test("a row is one tab-separated line", () => {
  expect(stamp(new Date("2026-11-16T09:08:07.123Z"))).toBe("2026-11-16T09:08:07Z");
  expect(verdictLine({ ...good, verdict: "wrong", reviewer: "r", at: "2026-11-16T09:08:07Z" } as never)).toBe(
    `${good.cut_id}\t4991a647\twrong\tok\tr\t2026-11-16T09:08:07Z\tv0.0.0-trial\n`,
  );
});
