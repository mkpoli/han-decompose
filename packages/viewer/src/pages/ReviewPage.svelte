<script lang="ts">
  import type { VerdictRow } from "han-decompose";
  import { cutsTable, postVerdict, verdicts as loadVerdicts, type Release } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import Help from "../ui/Help.svelte";
  import Loading from "../ui/Loading.svelte";
  import MenuSelect from "../ui/MenuSelect.svelte";
  import ReleaseGate from "../ui/ReleaseGate.svelte";
  import ReviewRow from "../ui/ReviewRow.svelte";

  const PAGE = 25;
  const editable = import.meta.env.DEV;

  interface Entry {
    row: Record<string, string>;
    score: number;
  }

  type VerdictFilter = "open" | "right" | "wrong" | "all";

  let font = $state("all");
  let source = $state("all");
  let method = $state("all");
  let filter = $state<VerdictFilter>("open");
  let at = $state(0);
  let shown = $state(PAGE);
  let given = $state<VerdictRow[]>([]);
  let failure = $state("");
  let entries = $state.raw<Entry[]>([]);
  let current: Release | null = null;

  async function load(rel: Release): Promise<void> {
    const [tables, known] = await Promise.all([Promise.all(rel.sources.sources.map((s) => cutsTable(s.id))), loadVerdicts()]);
    given = known;
    current = rel;
    entries = tables
      .flatMap((table) => table?.rows ?? [])
      .filter((row) => row.status === "accepted")
      .map((row) => ({ row, score: row.fit ? Number(row.fit) : Number.POSITIVE_INFINITY }))
      .sort((a, b) => a.score - b.score || (a.row.cut_id ?? "").localeCompare(b.row.cut_id ?? ""));
  }

  const key = (row: Record<string, string>): string => `${row.cut_id}|${row.sig}`;
  const decided = $derived(new Map(given.map((v) => [`${v.cut_id}|${v.sig}`, v.verdict])));
  const uniq = (entries: Entry[], column: string): string[] => [...new Set(entries.map((e) => e.row[column] ?? ""))].filter(Boolean).sort();

  async function judge(rel: Release, entry: Entry, verdict: VerdictRow["verdict"]): Promise<void> {
    failure = "";
    try {
      const row = await postVerdict({ cut_id: entry.row.cut_id ?? "", sig: entry.row.sig ?? "", verdict, note: "", release: rel.manifest.release });
      given = [...given, row];
    } catch {
      failure = t("review.failed");
    }
  }

  const list = $derived(
    entries.filter(
      (e) =>
        (font === "all" || e.row.font === font) &&
        (source === "all" || e.row.source === source) &&
        (method === "all" || e.row.method === method) &&
        (filter === "all" || (filter === "open" ? !decided.has(key(e.row)) : decided.get(key(e.row)) === filter)),
    ),
  );

  function onkey(event: KeyboardEvent): void {
    const target = event.target as HTMLElement | null;
    if (event.ctrlKey || event.metaKey || event.altKey || target?.closest("input, textarea, [role='menu'], dialog, [popover]")) return;
    const k = event.key.toLowerCase();
    if (k === "j") at = Math.min(at + 1, list.length - 1);
    else if (k === "k") at = Math.max(at - 1, 0);
    else if ((k === "r" || k === "w") && editable) {
      const entry = list[at];
      if (entry && current) void judge(current, entry, k === "r" ? "right" : "wrong");
    } else return;
    event.preventDefault();
    shown = Math.max(shown, at + 1);
    queueMicrotask(() => document.querySelector(".review.selected")?.scrollIntoView({ block: "nearest" }));
  }

  const reset = (): void => {
    at = 0;
    shown = PAGE;
  };
</script>

<svelte:window onkeydown={onkey} />

<div class="page-head">
  <h1>{t("review.title")}</h1>
  <Help>
    <p>{t("help.review.order")}</p>
    <p>{t("help.review.keys")}</p>
  </Help>
</div>

<ReleaseGate>
  {#snippet children(rel)}
    {#await load(rel)}
      <Loading />
    {:then}
      <div class="toolbar">
        <MenuSelect label={t("filter.font")} value={font} options={[{ value: "all", label: t("filter.all") }, ...uniq(entries, "font").map((value) => ({ value, label: value }))]} onchange={(v) => { font = v; reset(); }} />
        <MenuSelect label={t("filter.source")} value={source} options={[{ value: "all", label: t("filter.all") }, ...uniq(entries, "source").map((value) => ({ value, label: value }))]} onchange={(v) => { source = v; reset(); }} />
        <MenuSelect label={t("filter.method")} value={method} options={[{ value: "all", label: t("filter.all") }, ...uniq(entries, "method").map((value) => ({ value, label: value }))]} onchange={(v) => { method = v; reset(); }} />
        <MenuSelect
          label={t("filter.verdict")}
          value={filter}
          options={[
            { value: "open", label: t("verdict.open") },
            { value: "right", label: t("verdict.right") },
            { value: "wrong", label: t("verdict.wrong") },
            { value: "all", label: t("filter.all") },
          ]}
          onchange={(v) => { filter = v as VerdictFilter; reset(); }}
        />
        <span class="count num muted">{n(list.length)}</span>
      </div>
      {#if failure}<p class="failure" role="alert">{failure}</p>{/if}
      {#if !list.length}
        <div class="empty-note">{t("review.empty")}</div>
      {:else}
        <div class="queue">
          {#each list.slice(0, shown) as entry, i (key(entry.row))}
            <ReviewRow
              {rel}
              row={entry.row}
              selected={i === at}
              verdict={decided.get(key(entry.row)) ?? null}
              {editable}
              onselect={() => (at = i)}
              onverdict={(verdict) => void judge(rel, entry, verdict)}
            />
          {/each}
        </div>
        {#if shown < list.length}
          <div class="row"><button type="button" class="ui-button" onclick={() => (shown += PAGE)}>{t("library.more", { count: Math.min(PAGE, list.length - shown) })}</button></div>
        {/if}
      {/if}
    {/await}
  {/snippet}
</ReleaseGate>

<style>
  .queue {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-lg);
  }
  .count {
    align-self: center;
  }
  .failure {
    margin: 0;
    color: var(--ui-color-danger);
  }
</style>
