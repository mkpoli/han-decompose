<script lang="ts">
  import type { Skipped } from "han-decompose";
  import Ids from "./Ids.svelte";
  import ComponentLabel from "./ComponentLabel.svelte";

  let { skipped }: { skipped: Skipped } = $props();
</script>

<article class="skipped">
  <div class="line">
    <span class="ui-chip mono" data-variant="danger">{skipped.reason.code}</span>
    <span class="ids"><Ids text={skipped.ids} /></span>
    {#if !skipped.subject.startsWith("u:")}<ComponentLabel ref={skipped.subject} />{/if}
  </div>
  <p class="why">{skipped.reason.text}</p>
</article>

<style>
  .skipped {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-xs);
    padding: var(--ui-space-md) var(--ui-space-lg);
    border: 1px dashed var(--ui-color-border-strong);
    border-radius: var(--ui-radius-lg);
    min-inline-size: 0;
  }
  .line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--ui-space-xs) var(--ui-space-md);
  }
  .ids {
    overflow-wrap: anywhere;
  }
  .why {
    margin: 0;
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-sm);
  }
</style>
