<script lang="ts">
  // Waits for the release's manifest, fonts and sources, and says so where there is none.
  import type { Snippet } from "svelte";
  import { release, type Release } from "../lib/data.ts";
  import { t } from "../lib/i18n.svelte.ts";

  let { children }: { children: Snippet<[Release]> } = $props();
</script>

{#await release()}
  <div class="state"><span class="ui-spinner" role="status" aria-label={t("state.loading")}></span></div>
{:then rel}
  {@render children(rel)}
{:catch}
  <div class="state"><div class="ui-empty">{t("state.noRelease")}</div></div>
{/await}

<style>
  .state {
    display: grid;
    place-items: center;
    padding: var(--ui-space-4xl);
  }
</style>
