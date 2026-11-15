<script lang="ts">
  // A toggletip: a small button that opens a note. The note is where method and caveats live, so the
  // page itself carries labels and values only.
  import type { Snippet } from "svelte";
  import { t } from "../lib/i18n.svelte.ts";
  import Icon from "./Icon.svelte";

  let { label, children }: { label?: string; children: Snippet } = $props();

  const uid = $props.id();
  let trigger: HTMLButtonElement | null = $state(null);
  let tip: HTMLDivElement | null = $state(null);

  function place(event: ToggleEvent): void {
    if (event.newState !== "open" || !trigger || !tip) return;
    const box = trigger.getBoundingClientRect();
    const width = tip.offsetWidth;
    const left = Math.min(Math.max(box.left + box.width / 2 - width / 2, 8), Math.max(innerWidth - width - 8, 8));
    tip.style.left = `${left}px`;
    tip.style.top = `${box.bottom + 8}px`;
  }
</script>

<button bind:this={trigger} type="button" class="ui-button help" data-variant="quiet" data-size="icon" popovertarget={uid} aria-label={label ?? t("help.label")}>
  <Icon name="help" size={16} />
</button>
<div bind:this={tip} id={uid} class="tip" popover="auto" ontoggle={place}>{@render children()}</div>

<style>
  .help {
    min-block-size: var(--ui-control-h-xs);
    inline-size: var(--ui-control-h-sm);
    padding: 0;
  }
  .tip {
    position: fixed;
    inset: auto;
    margin: 0;
    inline-size: max-content;
    max-inline-size: min(360px, calc(100vw - 16px));
    padding: var(--ui-space-lg) var(--ui-space-xl);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
    color: var(--ui-color-ink);
    box-shadow: var(--ui-shadow-2);
    font-size: var(--ui-text-sm);
    line-height: var(--ui-leading-normal);
  }
  .tip :global(p) {
    margin: 0;
  }
  .tip :global(p + p) {
    margin-block-start: var(--ui-space-sm);
  }
</style>
