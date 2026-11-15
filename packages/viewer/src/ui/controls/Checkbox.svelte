<script lang="ts">
  // A checkbox as a native input with its label and an optional hint. The box, its states and
  // the keyboard behaviour come from the browser; design/controls.css draws them.
  let { checked = $bindable(false), indeterminate = false, label, hint, disabled = false, name, value, ariaLabel }: { checked?: boolean; indeterminate?: boolean; label: string; hint?: string; disabled?: boolean; name?: string; value?: string; ariaLabel?: string } = $props()
  let box: HTMLInputElement | null = $state(null)
  const uid = $props.id()
  $effect(() => { if (box) box.indeterminate = indeterminate })
</script>

<div class="ui-check-field">
  <label class="ui-check-row">
    <input bind:this={box} class="ui-checkbox" type="checkbox" bind:checked {disabled} {name} {value}
      aria-label={label ? undefined : ariaLabel} aria-describedby={hint ? `${uid}-hint` : undefined} />
    {#if label}<span class="ui-check-text"><span>{label}</span></span>{/if}
  </label>
  {#if hint}<span class="ui-hint ui-check-hint" id={`${uid}-hint`}>{hint}</span>{/if}
</div>
