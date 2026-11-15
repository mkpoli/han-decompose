<script lang="ts">
  import { charRows, type FontRow } from "../lib/char.ts";
  import { sourceOf } from "../lib/data.ts";
  import { selectorRef, selectorText } from "../lib/ids.ts";
  import { t } from "../lib/i18n.svelte.ts";
  import { routeHref } from "../lib/router.ts";
  import GlyphSvg from "../ui/GlyphSvg.svelte";
  import Help from "../ui/Help.svelte";
  import Icon from "../ui/Icon.svelte";
  import Loading from "../ui/Loading.svelte";
  import ReadingCard from "../ui/ReadingCard.svelte";
  import ReleaseGate from "../ui/ReleaseGate.svelte";
  import SkippedCard from "../ui/SkippedCard.svelte";
  import Glyph from "../ui/Glyph.svelte";

  let { id, font }: { id: string; font?: string | undefined } = $props();
  const componentRef = $derived(selectorRef(id));

  const sourcesOf = (rows: FontRow[]): string[] => [...new Set(rows.flatMap((r) => r.cells.filter((c) => c.readings.length || c.skipped.length).map((c) => c.source)))];
</script>

<div class="page-head">
  {#if componentRef}<h1 class="character"><Glyph selector={id} text={selectorText(id)} /></h1>{:else}<h1 class="mono">{id}</h1>{/if}
  <span class="ui-chip mono">{id}</span>
  {#if componentRef}
    <a class="ui-button" href={routeHref({ name: "component", ref: componentRef })}>{t("char.asComponent")}<Icon name="arrow-right" size={16} /></a>
  {/if}
  <Help>
    <p>{t("help.char.colours")}</p>
    <p>{t("help.char.refused")}</p>
  </Help>
</div>

<ReleaseGate>
  {#snippet children(rel)}
    {#await charRows(rel, id, font)}
      <Loading />
    {:then rows}
      {#if !rows.length}
        <div class="empty-note">{t("char.none")}</div>
      {:else}
        {@const sources = sourcesOf(rows)}
        {#each rows as row (row.font.id)}
          <section class="section font">
            <div class="section-head">
              <a class="font-name" href={routeHref({ name: "font", id: row.font.id })}>{row.font.name}</a>
              <span class="ui-chip">{row.chain}</span>
              <span class="ui-chip mono">{row.font.version}</span>
            </div>
            <div class="grid" style:--cols={sources.length}>
              <div class="cell plain-cell">
                <h3 class="source">{t("char.outline")}</h3>
                <div class="plain">
                  {#if row.glyph}
                    <GlyphSvg glyph={row.glyph} label={`${selectorText(id)} ${row.font.name}`} />
                  {:else}
                    <div class="ui-empty">{t("char.noOutline")}</div>
                  {/if}
                </div>
              </div>
              {#each sources as source (source)}
                {@const cell = row.cells.find((c) => c.source === source)}
                <div class="cell">
                  <h3 class="source" title={sourceOf(rel, source)?.name}>{source}</h3>
                  {#each cell?.readings ?? [] as reading (reading.description)}
                    <ReadingCard {reading} glyph={row.glyph} />
                  {/each}
                  {#each cell?.skipped ?? [] as skipped (skipped.description)}
                    <SkippedCard {skipped} />
                  {/each}
                  {#if !cell?.readings.length && !cell?.skipped.length}<span class="muted dash">–</span>{/if}
                </div>
              {/each}
            </div>
          </section>
        {/each}
      {/if}
    {/await}
  {/snippet}
</ReleaseGate>

<style>
  .character {
    font-size: var(--ui-text-2xl);
    line-height: 1;
  }
  .font-name {
    color: var(--ui-color-ink);
    font-size: var(--ui-text-lg);
    font-weight: var(--ui-weight-semibold);
    text-decoration: none;
  }
  .font-name:hover {
    color: var(--ui-color-accent);
  }
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--ui-space-xl);
    align-items: start;
  }
  .plain {
    inline-size: min(100%, 200px);
    padding: var(--ui-space-sm);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
  }
  .cell {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-md);
    min-inline-size: 0;
  }
  .source {
    color: var(--ui-color-ink-muted);
    font-family: var(--ui-font-mono);
    font-size: var(--ui-text-sm);
    font-weight: var(--ui-weight-medium);
  }
  .dash {
    padding-inline: var(--ui-space-sm);
  }
  @media (min-width: 720px) {
    .grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .plain-cell {
      grid-column: 1 / -1;
    }
  }
  @media (min-width: 1200px) {
    .grid {
      grid-template-columns: 200px repeat(var(--cols), minmax(0, 1fr));
    }
    .plain-cell {
      grid-column: auto;
    }
  }
</style>
