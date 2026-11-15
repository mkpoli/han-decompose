<script lang="ts">
  import { skippedTable, type Release } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import { selectorOfChar } from "../lib/ids.ts";
  import { routeHref } from "../lib/router.ts";
  import Glyph from "../ui/Glyph.svelte";
  import Ids from "../ui/Ids.svelte";
  import Help from "../ui/Help.svelte";
  import Icon from "../ui/Icon.svelte";
  import Loading from "../ui/Loading.svelte";
  import MenuSelect from "../ui/MenuSelect.svelte";
  import ReleaseGate from "../ui/ReleaseGate.svelte";

  const PAGE = 200;

  interface Row {
    font: string;
    glyph: string;
    char: string;
    source: string;
    description: string;
    ids: string;
    reason_code: string;
    reason: string;
  }

  let font = $state("all");
  let source = $state("all");
  let reason = $state("all");
  let page = $state(0);

  async function load(rel: Release): Promise<Row[]> {
    const tables = await Promise.all(rel.sources.sources.map((s) => skippedTable(s.id)));
    return tables.flatMap((table) => (table?.rows ?? []) as unknown as Row[]);
  }

  const uniq = (rows: Row[], key: (r: Row) => string): string[] => [...new Set(rows.map(key))].sort();

  function reset(): void {
    page = 0;
  }
</script>

<div class="page-head">
  <h1>{t("skipped.title")}</h1>
  <Help>
    <p>{t("help.skipped")}</p>
  </Help>
</div>

<ReleaseGate>
  {#snippet children(rel)}
    {#await load(rel)}
      <Loading />
    {:then rows}
      {@const scoped = rows.filter((r) => (font === "all" || r.font === font) && (source === "all" || r.source === source))}
      {@const counts = scoped.reduce((m, r) => m.set(r.reason_code, (m.get(r.reason_code) ?? 0) + 1), new Map<string, number>())}
      {@const matching = reason === "all" ? scoped : scoped.filter((r) => r.reason_code === reason)}
      {@const last = Math.max(Math.ceil(matching.length / PAGE) - 1, 0)}
      {@const at = Math.min(page, last)}
      {@const view = matching.slice(at * PAGE, (at + 1) * PAGE)}
      <div class="toolbar">
        <MenuSelect
          label={t("filter.font")}
          value={font}
          options={[{ value: "all", label: t("filter.all") }, ...uniq(rows, (r) => r.font).map((value) => ({ value, label: value }))]}
          onchange={(v) => {
            font = v;
            reset();
          }}
        />
        <MenuSelect
          label={t("filter.source")}
          value={source}
          options={[{ value: "all", label: t("filter.all") }, ...uniq(rows, (r) => r.source).map((value) => ({ value, label: value }))]}
          onchange={(v) => {
            source = v;
            reset();
          }}
        />
      </div>
      <div class="row" role="group" aria-label={t("skipped.reasons")}>
        <button type="button" class="ui-chip" data-interactive aria-current={reason === "all"} onclick={() => { reason = "all"; reset(); }}>{t("filter.all")} <span class="num">{n(scoped.length)}</span></button>
        {#each [...counts].sort((a, b) => b[1] - a[1]) as [code, count] (code)}
          <button type="button" class="ui-chip" data-interactive aria-current={reason === code} onclick={() => { reason = code; reset(); }}>
            <span class="mono">{code}</span> <span class="num">{n(count)}</span>
          </button>
        {/each}
      </div>

      {#if !matching.length}
        <div class="empty-note">{t("skipped.none")}</div>
      {:else}
        <div class="scroll-x">
          <table class="data">
            <thead>
              <tr><th>{t("skipped.character")}</th><th>{t("skipped.ids")}</th><th>{t("skipped.reason")}</th><th class="wide">{t("filter.font")}</th><th class="wide">{t("filter.source")}</th></tr>
            </thead>
            <tbody>
              {#each view as row, i (at * PAGE + i)}
                {@const selector = row.glyph ? row.glyph : row.char ? selectorOfChar(row.char) : null}
                <tr>
                  <td class="char">
                    {#if selector}
                      <a href={routeHref({ name: "char", id: selector })}><Glyph {selector} text={row.char || undefined} /> <span class="mono muted">{selector}</span></a>
                    {:else}–{/if}
                  </td>
                  <td class="ids"><Ids text={row.ids} /></td>
                  <td class="why"><span class="ui-chip mono" data-variant="danger">{row.reason_code}</span><span class="muted">{row.reason}</span></td>
                  <td class="mono wide">{row.font}</td>
                  <td class="mono wide">{row.source}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="row pager">
          <button type="button" class="ui-button" data-size="icon" aria-label={t("pager.previous")} disabled={at === 0} onclick={() => (page = at - 1)}><Icon name="left" /></button>
          <span class="num muted">{t("pager.range", { from: n(at * PAGE + 1), to: n(Math.min((at + 1) * PAGE, matching.length)), total: n(matching.length) })}</span>
          <button type="button" class="ui-button" data-size="icon" aria-label={t("pager.next")} disabled={at >= last} onclick={() => (page = at + 1)}><Icon name="right" /></button>
        </div>
      {/if}
    {/await}
  {/snippet}
</ReleaseGate>

<style>
  .char {
    white-space: nowrap;
    font-size: var(--ui-text-lg);
  }
  .ids {
    font-size: var(--ui-text-md);
    min-inline-size: 140px;
    overflow-wrap: anywhere;
  }
  .why {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--ui-space-2xs);
    min-inline-size: 220px;
  }
  @media (max-width: 719px) {
    .wide {
      display: none;
    }
  }
  .pager {
    justify-content: center;
  }
</style>
