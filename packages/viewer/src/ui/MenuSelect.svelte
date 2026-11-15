<script lang="ts">
  // One choice out of a list, as a button that opens a menu. Arrow keys, Home, End and typing move,
  // Enter or Space chooses, Escape closes and returns the focus. It replaces a native select.
  import { tick } from "svelte";
  import Icon from "./Icon.svelte";

  interface Option {
    value: string;
    label: string;
    note?: string;
  }

  let {
    label,
    value,
    options,
    onchange,
    icon,
    compact = false,
    align = "start",
    hideLabel = false,
  }: {
    label: string;
    value: string;
    options: Option[];
    onchange: (value: string) => void;
    icon?: string;
    /** Only the icon on the button. */
    compact?: boolean;
    align?: "start" | "end";
    /** The label is the button's accessible name only. */
    hideLabel?: boolean;
  } = $props();

  const uid = $props.id();
  let open = $state(false);
  let root: HTMLElement | null = $state(null);
  let trigger: HTMLButtonElement | null = $state(null);
  let menu: HTMLElement | null = $state(null);
  let flip = $state(false);
  let typed = "";
  let typedAt = 0;

  const current = $derived(options.find((o) => o.value === value));
  const items = (): HTMLElement[] => [...(menu?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? [])];

  async function show(): Promise<void> {
    open = true;
    flip = false;
    await tick();
    if (menu && trigger) {
      const box = menu.getBoundingClientRect();
      flip = align === "end" ? box.left < 8 : box.right > innerWidth - 8;
    }
    (menu?.querySelector<HTMLElement>('[aria-checked="true"]') ?? items()[0])?.focus();
  }

  function hide(refocus = false): void {
    open = false;
    if (refocus) trigger?.focus();
  }

  function choose(next: string): void {
    hide(true);
    if (next !== value) onchange(next);
  }

  function triggerKey(event: KeyboardEvent): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      void show();
    }
  }

  function menuKey(event: KeyboardEvent): void {
    event.stopPropagation();
    const list = items();
    const at = list.indexOf(document.activeElement as HTMLElement);
    if (event.key === "Escape") {
      event.preventDefault();
      hide(true);
    } else if (event.key === "Tab") hide();
    else if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      list[at]?.click();
    } else {
      const to: Record<string, number> = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: list.length - 1 };
      const target = to[event.key];
      if (target !== undefined) {
        event.preventDefault();
        list[(target + list.length) % list.length]?.focus();
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
        const now = Date.now();
        typed = now - typedAt > 700 ? event.key.toLowerCase() : typed + event.key.toLowerCase();
        typedAt = now;
        list.find((el) => el.textContent?.trim().toLowerCase().startsWith(typed))?.focus();
      }
    }
  }

  $effect(() => {
    if (!open) return;
    const away = (event: Event): void => {
      if (root && !event.composedPath().includes(root)) hide();
    };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  });
</script>

<div class="select" class:block={!compact} bind:this={root}>
  {#if !hideLabel && !compact}<span class="ui-label" id={`${uid}-label`}>{label}</span>{/if}
  <button
    bind:this={trigger}
    type="button"
    class="ui-button trigger"
    aria-haspopup="menu"
    aria-expanded={open}
    aria-label={compact || hideLabel ? `${label}: ${current?.label ?? ""}` : undefined}
    aria-labelledby={compact || hideLabel ? undefined : `${uid}-label ${uid}-value`}
    title={compact ? `${label}: ${current?.label ?? ""}` : undefined}
    onclick={() => (open ? hide() : void show())}
    onkeydown={triggerKey}
  >
    {#if icon}<Icon name={icon} size={16} />{/if}
    {#if !compact}<span class="value" id={`${uid}-value`}>{current?.label ?? ""}</span>{/if}
    <span class="chev" class:up={open}><Icon name="chevron" size={14} /></span>
  </button>
  {#if open}
    <div class="ui-menu menu" class:end={align === "end" ? !flip : flip} role="menu" tabindex="-1" aria-label={label} bind:this={menu} onkeydown={menuKey}>
      {#each options as option (option.value)}
        <button type="button" class="ui-menu-item" role="menuitemradio" aria-checked={option.value === value} tabindex="-1" onclick={() => choose(option.value)}>
          <span class="text">{option.label}</span>
          {#if option.note}<span class="note">{option.note}</span>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .select {
    position: relative;
    display: inline-flex;
    flex-direction: column;
    gap: var(--ui-space-2xs);
    min-inline-size: 0;
  }
  .select.block {
    min-inline-size: 140px;
  }
  .trigger {
    justify-content: space-between;
    inline-size: 100%;
    font-weight: var(--ui-weight-normal);
    font-size: var(--ui-text-md);
  }
  .select:not(.block) .trigger {
    inline-size: auto;
  }
  .value {
    flex: 1;
    min-inline-size: 0;
    overflow: hidden;
    text-align: start;
    text-overflow: ellipsis;
  }
  .chev {
    display: grid;
    color: var(--ui-color-ink-muted);
    transition: transform var(--ui-duration-fast);
  }
  .chev.up {
    transform: rotate(180deg);
  }
  .menu {
    position: absolute;
    z-index: var(--ui-z-menu);
    inset-block-start: 100%;
    inset-inline-start: 0;
    margin-block-start: var(--ui-space-2xs);
    inline-size: max-content;
    min-inline-size: 100%;
    max-inline-size: calc(100vw - 2 * var(--ui-space-xl));
    max-block-size: min(60vh, 360px);
    overflow-y: auto;
  }
  .menu.end {
    inset-inline-start: auto;
    inset-inline-end: 0;
  }
  .text {
    flex: 1;
    min-inline-size: 0;
  }
  .note {
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-xs);
    font-variant-numeric: tabular-nums;
  }
</style>
