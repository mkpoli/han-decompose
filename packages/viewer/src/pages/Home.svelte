<script lang="ts">
  import { knownComponents } from "../lib/components.ts";
  import { type Release } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import { go } from "../lib/nav.svelte.ts";
  import { routeHref } from "../lib/router.ts";
  import { search, type Hit } from "../lib/search.ts";
  import { chainFonts } from "../lib/data.ts";
  import ComponentLabel from "../ui/ComponentLabel.svelte";
  import Glyph from "../ui/Glyph.svelte";
  import ReleaseGate from "../ui/ReleaseGate.svelte";
  import TextField from "../ui/controls/TextField.svelte";

  let query = $state("");
  let components = $state<ReadonlySet<string>>(new Set());
  let loaded = false;

  function load(rel: Release): void {
    if (loaded) return;
    loaded = true;
    void knownComponents(rel).then((set) => (components = set));
  }

  const href = (hit: Hit): string =>
    hit.kind === "char" ? routeHref({ name: "char", id: hit.id }) : hit.kind === "component" ? routeHref({ name: "component", ref: hit.ref }) : routeHref({ name: "font", id: hit.id });

  function totals(rel: Release): { readings: number; cuts: number; skipped: number } {
    let readings = 0;
    let cuts = 0;
    let skipped = 0;
    for (const sources of Object.values(rel.manifest.counts))
      for (const c of Object.values(sources)) {
        readings += c.readings ?? 0;
        skipped += c.skipped ?? 0;
        cuts += Object.values(c.cuts ?? {}).reduce((a, b) => a + (b ?? 0), 0);
      }
    return { readings, cuts, skipped };
  }
</script>

<ReleaseGate>
  {#snippet children(rel)}
    {@const hits = search(query, { fonts: rel.fonts.fonts, components })}
    {@const sum = totals(rel)}
    <section class="section find">
      <form
        onsubmit={(event) => {
          event.preventDefault();
          const first = hits[0];
          if (first) go(href(first));
        }}
      >
        <TextField label={t("home.search")} type="search" bind:value={query} placeholder={t("home.placeholder")} autocomplete="off" spellcheck={false} oninput={() => load(rel)} />
      </form>
      {#if query.trim()}
        <ul class="ui-list hits" aria-label={t("home.results")}>
          {#each hits as hit (hit.kind + (hit.kind === "char" ? hit.id : hit.kind === "component" ? hit.ref : hit.id))}
            <li>
              <a class="ui-list-row" data-interactive href={href(hit)}>
                <span class="ui-chip">{t(`kind.${hit.kind}`)}</span>
                {#if hit.kind === "char"}
                  <span class="big"><Glyph selector={hit.id} text={hit.text} /></span>
                  <span class="mono muted">{hit.id}</span>
                {:else if hit.kind === "component"}
                  <span class="big"><ComponentLabel ref={hit.ref} text={hit.text} plain /></span>
                  <span class="mono muted">{hit.ref}</span>
                {:else}
                  <span>{hit.name}</span>
                  <span class="mono muted">{hit.id}</span>
                {/if}
              </a>
            </li>
          {:else}
            <li class="ui-empty">{t("home.none")}</li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="section">
      <h2>{t("home.chains")}</h2>
      <div class="chains">
        {#each chainFonts(rel) as { chain, fonts } (chain)}
          <div class="ui-card chain">
            <h3>{chain}</h3>
            <ol class="ui-list">
              {#each fonts as font (font.id)}
                <li>
                  <a class="ui-list-row" data-interactive href={routeHref({ name: "font", id: font.id })}>
                    <span class="ui-list-row-label">{font.name}</span>
                    <span class="mono muted">{font.version}</span>
                    <span class="ui-chip">{font.licence}</span>
                  </a>
                </li>
              {/each}
            </ol>
          </div>
        {/each}
      </div>
    </section>

    <section class="section">
      <h2>{t("home.release")}</h2>
      <dl class="stats">
        <div class="stat"><dt>{t("home.name")}</dt><dd class="mono">{rel.manifest.release}</dd></div>
        <div class="stat"><dt>{t("home.tool")}</dt><dd class="mono tool">{rel.manifest.tool.name} {rel.manifest.tool.version}</dd></div>
        <div class="stat"><dt>{t("home.fonts")}</dt><dd class="num">{n(rel.fonts.fonts.length)}</dd></div>
        <div class="stat"><dt>{t("home.sources")}</dt><dd class="num">{n(rel.sources.sources.length)}</dd></div>
        <div class="stat"><dt>{t("count.readings")}</dt><dd class="num">{n(sum.readings)}</dd></div>
        <div class="stat"><dt>{t("count.cuts")}</dt><dd class="num">{n(sum.cuts)}</dd></div>
        <div class="stat"><dt>{t("count.skipped")}</dt><dd class="num">{n(sum.skipped)}</dd></div>
      </dl>
    </section>
  {/snippet}
</ReleaseGate>

<style>
  .find {
    max-inline-size: 720px;
  }
  .find :global(.ui-input) {
    font-family: var(--ids-font);
  }
  .hits {
    margin-block-start: var(--ui-space-xs);
  }
  .big {
    font-size: var(--ui-text-xl);
    line-height: 1;
  }
  .chains {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
    gap: var(--ui-space-xl);
  }
  .chain {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-md);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr));
    align-items: stretch;
    gap: var(--ui-space-md);
    margin: 0;
  }
  .stat {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    gap: var(--ui-space-2xs);
    padding: var(--ui-space-lg) var(--ui-space-xl);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
    min-inline-size: 0;
  }
  .stat dd {
    margin: 0;
    font-size: var(--ui-text-lg);
    font-weight: var(--ui-weight-semibold);
    overflow-wrap: anywhere;
  }
  .stat dd.tool {
    font-size: var(--ui-text-md);
    line-height: 1.6;
  }
  .stat dt {
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-xs);
  }
</style>
