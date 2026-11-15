<script lang="ts">
  // A glyph drawn from its outline: the em square with y up, the ink in the current colour. Sets of
  // contours are painted over the ink, each in one colour; a refused cut is hatched, never coloured.
  import type { Glyph } from "han-decompose";
  import { contoursPath, EM_VIEWBOX } from "../lib/path.ts";
  import type { Paint } from "../lib/reading.ts";

  let {
    glyph,
    viewBox = EM_VIEWBOX,
    base = "ink",
    paints = [],
    hot = null,
    onhot,
    label,
  }: {
    glyph: Glyph;
    viewBox?: string;
    base?: "ink" | "faint" | "none";
    paints?: Paint[];
    hot?: string | null;
    onhot?: (id: string | null) => void;
    label?: string;
  } = $props();

  const uid = $props.id();
  const hatch = `${uid}-hatch`;
  const whole = $derived(base === "none" ? "" : contoursPath(glyph));
  const shapes = $derived(paints.map((p) => ({ ...p, d: contoursPath(glyph, p.contours) })));
</script>

<svg class="glyph" {viewBox} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : "true"}>
  {#if shapes.some((s) => s.refused)}
    <defs>
      <pattern id={hatch} patternUnits="userSpaceOnUse" width="36" height="36" patternTransform="rotate(45)">
        <rect width="36" height="36" class="hatch-ground" />
        <rect width="14" height="36" class="hatch-line" />
      </pattern>
    </defs>
  {/if}
  {#if whole}<path d={whole} class="base" class:faint={base === "faint"} />{/if}
  {#each shapes as shape (shape.id)}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <path
      d={shape.d}
      class="paint"
      class:refused={shape.refused}
      class:dim={hot !== null && hot !== shape.id}
      class:hot={hot === shape.id}
      style:fill={shape.refused ? `url(#${hatch})` : (shape.colour ?? "currentColor")}
      onpointerenter={() => onhot?.(shape.id)}
      onpointerleave={() => onhot?.(null)}
    />
  {/each}
</svg>

<style>
  .glyph {
    display: block;
    inline-size: 100%;
    block-size: auto;
    aspect-ratio: 1;
    overflow: visible;
  }
  .base {
    fill: currentColor;
  }
  .base.faint {
    opacity: 0.16;
  }
  .paint {
    transition: opacity var(--ui-duration-fast) var(--ui-ease);
  }
  .paint.refused {
    stroke: var(--ui-color-danger);
    stroke-width: 6;
    stroke-dasharray: 18 10;
  }
  .paint.dim {
    opacity: 0.25;
  }
  .paint.hot {
    stroke: var(--ui-color-ink);
    stroke-width: 12;
    stroke-dasharray: none;
    paint-order: stroke;
  }
  .hatch-ground {
    fill: var(--ui-color-danger-soft);
  }
  .hatch-line {
    fill: var(--ui-color-danger);
  }
</style>
