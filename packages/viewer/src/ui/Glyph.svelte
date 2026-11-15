<script lang="ts">
  // One character inside text. A character most machines cannot draw is drawn from its outline where
  // the release has one; any other is text.
  import { drawn, release } from "../lib/data.ts";
  import { needsOutline, parseSelector, selectorText } from "../lib/ids.ts";
  import { contoursPath, EM_VIEWBOX } from "../lib/path.ts";

  let { selector, text }: { selector: string; text?: string } = $props();

  const shown = $derived(text ?? selectorText(selector));
  const cp = $derived(parseSelector(selector)?.cp ?? null);
  const outline = $derived(cp !== null && needsOutline(cp) ? release().then((r) => drawn(r, selector)).catch(() => null) : null);
</script>

{#if outline}
  {#await outline}
    <span class="han pending" aria-hidden="true"></span>
  {:then found}
    {#if found}
      <svg class="han outline" viewBox={EM_VIEWBOX} role="img" aria-label={shown}><path d={contoursPath(found.glyph)} /></svg>
    {:else}
      <span class="han">{shown}</span>
    {/if}
  {/await}
{:else}
  <span class="han">{shown}</span>
{/if}

<style>
  .han {
    font-family: var(--hd-cjk);
  }
  .outline,
  .pending {
    display: inline-block;
    inline-size: 1em;
    block-size: 1em;
    vertical-align: -0.12em;
    fill: currentColor;
  }
</style>
