<script lang="ts">
  // A cut drawn small: its contours in the colour of their node inside the host glyph in faint ink,
  // or alone, cropped to its box. It links to the host's page.
  import type { ResolvedCut } from "../lib/data.ts";
  import { n } from "../lib/i18n.svelte.ts";
  import { boxViewBox, EM_VIEWBOX } from "../lib/path.ts";
  import { routeHref } from "../lib/router.ts";
  import { isRefused, nodeColour, nodeIndex, pathKey, score } from "../lib/reading.ts";
  import GlyphSvg from "./GlyphSvg.svelte";

  let { resolved, alone = false, caption = true }: { resolved: ResolvedCut; alone?: boolean; caption?: boolean } = $props();

  const cut = $derived(resolved.cut);
  const colour = $derived(nodeColour(nodeIndex(resolved.reading).get(pathKey(cut.path)) ?? 0));
  const value = $derived(score(cut));
</script>

<a class="tile" href={routeHref({ name: "char", id: resolved.selector })} title={cut.id}>
  {#if resolved.glyph}
    <span class="draw">
      <GlyphSvg
        glyph={resolved.glyph}
        viewBox={alone ? boxViewBox(cut.box) : EM_VIEWBOX}
        base={alone ? "none" : "faint"}
        paints={[{ id: cut.id, contours: cut.contours, colour: alone ? "currentColor" : colour, refused: isRefused(cut) }]}
      />
    </span>
  {/if}
  {#if caption}
    <span class="caption num">
      <span>{value === undefined ? "–" : n(value)}</span>
    </span>
  {/if}
</a>

<style>
  .tile {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-2xs);
    padding: var(--ui-space-xs);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-md);
    background: var(--ui-color-surface);
    color: var(--ui-color-ink);
    text-decoration: none;
  }
  .tile:hover {
    border-color: var(--ui-color-border-strong);
    background: var(--ui-color-surface-hover);
  }
  .draw {
    display: block;
  }
  .caption {
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-xs);
    text-align: center;
  }
</style>
