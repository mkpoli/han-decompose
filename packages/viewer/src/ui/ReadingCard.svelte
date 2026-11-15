<script lang="ts">
  // One reading: the description, the glyph with each cut painted in the colour of its node, and the
  // list of cuts. A row and its contours light up together.
  import type { Cut, Glyph, Reading } from "han-decompose";
  import { componentText } from "../lib/ids.ts";
  import { n, t, tx } from "../lib/i18n.svelte.ts";
  import { byPath, isRefused, layers, nodeColour, nodeIndex, pathKey, type Paint } from "../lib/reading.ts";
  import ComponentLabel from "./ComponentLabel.svelte";
  import Ids from "./Ids.svelte";
  import GlyphSvg from "./GlyphSvg.svelte";

  let { reading, glyph }: { reading: Reading; glyph: Glyph | null } = $props();

  let hot = $state<string | null>(null);
  const index = $derived(nodeIndex(reading));
  const colour = (cut: Cut): string => nodeColour(index.get(pathKey(cut.path)) ?? 0);
  const paints = $derived<Paint[]>(layers(reading).map((l) => ({ id: l.cut.id, contours: l.contours, refused: isRefused(l.cut), colour: colour(l.cut) })));
  const rows = $derived(byPath(reading.cuts));
  const evidence = (cut: Cut): [string, number][] => {
    const e = cut.evidence ?? {};
    const out: [string, number | undefined][] = [["fit", e.fit], ["match", e.match], ["margin", e.margin], ["agree", e.agree], ["reference", e.reference]];
    return out.filter((x): x is [string, number] => x[1] !== undefined);
  };
</script>

<article class="reading">
  <header class="head">
    <span class="ids"><Ids text={reading.ids} /></span>
    <span class="chips">
      {#each (reading.tags ?? "").split(" ").filter(Boolean) as tag (tag)}<span class="ui-chip">{tag}</span>{/each}
      <span class="ui-chip">{reading.method.name}</span>
      {#if reading.method.grain}<span class="ui-chip">{t(`grain.${reading.method.grain}`)}</span>{/if}
      <span class="ui-chip" data-variant={reading.complete ? "accent" : undefined}>{reading.complete ? t("reading.complete") : t("reading.partial")}</span>
    </span>
  </header>

  <div class="body">
    {#if glyph}
      <div class="draw"><GlyphSvg {glyph} base="faint" {paints} {hot} onhot={(id) => (hot = id)} label={reading.ids} /></div>
    {/if}
    <ul class="cuts">
      {#each rows as cut (cut.id)}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions, a11y_no_noninteractive_tabindex -->
        <li
          class="cut"
          class:on={hot === cut.id}
          tabindex="0"
          style:--depth={cut.path.length}
          onpointerenter={() => (hot = cut.id)}
          onpointerleave={() => (hot = null)}
          onfocus={() => (hot = cut.id)}
          onblur={() => (hot = null)}
        >
          <span class="swatch" class:refused={isRefused(cut)} style:--swatch={colour(cut)} aria-hidden="true"></span>
          <span class="what">
            <span class="text"><ComponentLabel ref={cut.component} text={cut.text || componentText(cut.component)} /></span>
            <span class="meta">
              {#if cut.place}<span class="ui-chip mono">{cut.place}</span>{/if}
              <span class="ui-chip status" data-variant={isRefused(cut) ? "danger" : cut.status.startsWith("reviewed") ? "accent" : undefined}>{t(`status.${cut.status}`)}</span>
            </span>
          </span>
          {#if evidence(cut).length}
            <span class="evidence num">
              {#each evidence(cut) as [name, value] (name)}<span title={tx(`evidence.${name}`)}>{tx(`evidence.${name}`)} {n(value)}</span>{/each}
            </span>
          {/if}
        </li>
      {/each}
    </ul>
  </div>
  {#if !reading.cuts.length}<p class="muted">{t("reading.noCuts")}</p>{/if}
</article>

<style>
  .reading {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-md);
    padding: var(--ui-space-lg);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
    min-inline-size: 0;
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-xs);
  }
  .ids {
    font-size: var(--ui-text-lg);
    overflow-wrap: anywhere;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ui-space-xs);
  }
  .body {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--ui-space-md);
  }
  .draw {
    inline-size: min(100%, 220px);
    color: var(--ui-color-ink);
  }
  .cuts {
    display: flex;
    flex-direction: column;
    gap: 1px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .cut {
    display: grid;
    grid-template-columns: 14px minmax(0, 1fr);
    gap: var(--ui-space-xs) var(--ui-space-sm);
    padding: var(--ui-space-xs) var(--ui-space-sm);
    padding-inline-start: calc(var(--ui-space-sm) + (var(--depth) - 1) * var(--ui-space-lg));
    border-radius: var(--ui-radius-sm);
    font-size: var(--ui-text-md);
  }
  .cut:hover,
  .cut.on {
    background: var(--ui-color-surface-hover);
  }
  .swatch {
    inline-size: 14px;
    block-size: 14px;
    margin-block-start: 4px;
    border-radius: var(--ui-radius-xs);
    background: var(--swatch);
  }
  .swatch.refused {
    background: repeating-linear-gradient(45deg, var(--ui-color-danger) 0 2px, var(--ui-color-danger-soft) 2px 5px);
    outline: 1px dashed var(--ui-color-danger);
    outline-offset: -1px;
  }
  .what {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--ui-space-xs) var(--ui-space-md);
  }
  .text {
    font-size: var(--ui-text-lg);
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ui-space-xs);
  }
  .evidence {
    grid-column: 2;
    display: flex;
    flex-wrap: wrap;
    gap: 0 var(--ui-space-lg);
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-xs);
  }
  @media (min-width: 520px) and (max-width: 899px) {
    .body {
      grid-template-columns: 200px minmax(0, 1fr);
      align-items: start;
    }
  }
</style>
