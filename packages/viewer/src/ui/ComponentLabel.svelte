<script lang="ts">
  // A component as a link to its page: the glyph that stands for it, where there is one, and its reference.
  import { referenceGlyph } from "../lib/components.ts";
  import { release } from "../lib/data.ts";
  import { componentText, refSelector } from "../lib/ids.ts";
  import { contoursPath, EM_VIEWBOX } from "../lib/path.ts";
  import { routeHref } from "../lib/router.ts";
  import Ids from "./Ids.svelte";
  import Glyph from "./Glyph.svelte";

  let { ref, text, plain = false }: { ref: string; text?: string; plain?: boolean } = $props();

  const selector = $derived(refSelector(ref));
  const label = $derived(text ?? componentText(ref));
  const numbered = $derived(ref.startsWith("bs:") ? release().then((r) => referenceGlyph(r, ref)).catch(() => null) : null);
</script>

{#snippet face()}
  {#if selector}
    <Glyph {selector} />
  {:else if numbered}
    {#await numbered then found}
      {#if found}
        <svg class="drawn" viewBox={EM_VIEWBOX} aria-hidden="true"><path d={contoursPath(found.glyph)} /></svg>
      {/if}
    {/await}
    <span class="code">{label}</span>
  {:else}
    <span class="code"><Ids text={label} /></span>
  {/if}
{/snippet}

{#if plain}
  <span class="component">{@render face()}</span>
{:else}
  <a class="component" href={routeHref({ name: "component", ref })} title={ref}>{@render face()}</a>
{/if}

<style>
  .component {
    display: inline-flex;
    align-items: baseline;
    gap: var(--ui-space-2xs);
    color: inherit;
    text-decoration: none;
  }
  a.component:hover {
    color: var(--ui-color-accent);
  }
  .drawn {
    inline-size: 1.1em;
    block-size: 1.1em;
    align-self: center;
    fill: currentColor;
  }
  .code {
    font-family: var(--hd-cjk);
    font-size: 0.9em;
  }
</style>
