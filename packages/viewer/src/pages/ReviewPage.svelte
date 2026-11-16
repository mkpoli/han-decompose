<script lang="ts">
  import type { VerdictRow } from "../lib/format1";
  import { chainOf, cutTableSources, forms, postVerdict, verdicts as loadVerdicts, weakestCuts, type QueueRow, type Release } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import Help from "../ui/Help.svelte";
  import Loading from "../ui/Loading.svelte";
  import MenuSelect from "../ui/MenuSelect.svelte";
  import ReleaseGate from "../ui/ReleaseGate.svelte";
  import ReviewRow from "../ui/ReviewRow.svelte";

  const PAGE = 25;
  const KEPT = 2000;
  const editable = import.meta.env.DEV;

  type VerdictFilter = "open" | "right" | "wrong" | "all";
  type Group = "accepted" | "refused" | "reviewed";
  const GROUPS: Record<Group, string[]> = { accepted: ["accepted"], refused: ["refused"], reviewed: ["reviewed-right", "reviewed-wrong"] };
  const BASES = ["reference", "agree", "single", "imported", "hand", "none"] as const;

  let source = $state("");
  let group = $state<Group>("accepted");
  let font = $state("all");
  let method = $state("all");
  let basis = $state("all");
  let filter = $state<VerdictFilter>("open");
  let at = $state(0);
  let shown = $state(PAGE);
  let given = $state<VerdictRow[]>([]);
  let failure = $state("");
  let entries = $state.raw<QueueRow[]>([]);
  let sources = $state<string[]>([]);
  let bases = $state.raw<Map<string, string>>(new Map());
  let busy = $state(true);
  let current: Release | null = null;

  async function start(rel: Release): Promise<void> {
    current = rel;
    const [list, known] = await Promise.all([cutTableSources(rel), loadVerdicts()]);
    given = known;
    sources = list;
    // The basis of a component's form, by chain and component.
    const map = new Map<string, string>();
    for (const chain of Object.keys(rel.fonts.chains)) for (const [ref, form] of Object.entries((await forms(chain))?.forms ?? {})) map.set(`${chain}|${ref}`, form.basis);
    bases = map;
    if (list[0] && !source) source = list[0];
    await reload();
  }

  async function reload(): Promise<void> {
    if (!source) {
      busy = false;
      return;
    }
    busy = true;
    try {
      entries = await weakestCuts(source, GROUPS[group], KEPT);
    } catch {
      entries = [];
      failure = t("review.failed");
    }
    at = 0;
    shown = PAGE;
    busy = false;
  }

  const key = (row: QueueRow): string => `${row.cut_id}|${row.sig}`;
  const decided = $derived(new Map(given.map((v) => [`${v.cut_id}|${v.sig}`, v.verdict])));
  const basisOf = (row: QueueRow): string => {
    const chain = current ? chainOf(current, row.font) : undefined;
    return (chain && bases.get(`${chain}|${row.component}`)) || "none";
  };
  const uniq = (column: "font" | "method"): string[] => [...new Set(entries.map((e) => e[column]))].filter(Boolean).sort();

  const list = $derived(
    entries.filter(
      (e) =>
        (font === "all" || e.font === font) &&
        (method === "all" || e.method === method) &&
        (basis === "all" || basisOf(e) === basis) &&
        (filter === "all" || (filter === "open" ? !decided.has(key(e)) : decided.get(key(e)) === filter)),
    ),
  );

  async function judge(rel: Release, entry: QueueRow, verdict: VerdictRow["verdict"]): Promise<void> {
    failure = "";
    try {
      const row = await postVerdict({ cut_id: entry.cut_id, sig: entry.sig, verdict, note: "", release: rel.manifest.release });
      given = [...given, row];
    } catch {
      failure = t("review.failed");
    }
  }

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
  const all = (label: string) => ({ value: "all", label });
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
    {#await start(rel)}
      <Loading />
    {:then}
      {#if !sources.length}
        <div class="empty-note">{t("review.empty")}</div>
      {:else}
        <div class="toolbar">
          <MenuSelect label={t("filter.source")} value={source} options={sources.map((value) => ({ value, label: value }))} onchange={(v) => { source = v; font = "all"; method = "all"; void reload(); }} />
          <MenuSelect
            label={t("filter.status")}
            value={group}
            options={[
              { value: "accepted", label: t("status.accepted") },
              { value: "refused", label: t("status.refused") },
              { value: "reviewed", label: t("status.reviewed") },
            ]}
            onchange={(v) => { group = v as Group; void reload(); }}
          />
          <MenuSelect label={t("filter.font")} value={font} options={[all(t("filter.all")), ...uniq("font").map((value) => ({ value, label: value }))]} onchange={(v) => { font = v; reset(); }} />
          <MenuSelect label={t("filter.method")} value={method} options={[all(t("filter.all")), ...uniq("method").map((value) => ({ value, label: value }))]} onchange={(v) => { method = v; reset(); }} />
          <MenuSelect label={t("filter.basis")} value={basis} options={[all(t("filter.all")), ...BASES.map((value) => ({ value, label: value === "none" ? t("basis.none") : t(`basis.${value}`) }))]} onchange={(v) => { basis = v; reset(); }} />
          <MenuSelect
            label={t("filter.verdict")}
            value={filter}
            options={[
              { value: "open", label: t("verdict.open") },
              { value: "right", label: t("verdict.right") },
              { value: "wrong", label: t("verdict.wrong") },
              all(t("filter.all")),
            ]}
            onchange={(v) => { filter = v as VerdictFilter; reset(); }}
          />
          <span class="count num muted">{n(list.length)}</span>
        </div>
        {#if failure}<p class="failure" role="alert">{failure}</p>{/if}
        {#if busy}
          <Loading />
        {:else if !list.length}
          <div class="empty-note">{t("review.empty")}</div>
        {:else}
          <div class="queue">
            {#each list.slice(0, shown) as entry, i (key(entry))}
              <ReviewRow
                {rel}
                row={{ cut_id: entry.cut_id, sig: entry.sig }}
                selected={i === at}
                verdict={decided.get(key(entry)) ?? null}
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
      {/if}
    {/await}
  {/snippet}
</ReleaseGate>

<style>
  .queue {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 560px), 1fr));
    align-items: start;
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
