<script lang="ts">
  // A description sequence as text. Machines often lack the ideographic description characters, so
  // each is drawn as a small box showing how it divides its operands.
  let { text }: { text: string } = $props();

  import { OPERATOR_LINES as LINES } from "../lib/operators.ts";
  const parts = $derived([...text].map((char) => ({ char, lines: LINES[char] })));
</script>

<span class="ids han">{#each parts as part, i (i)}{#if part.lines}<svg class="op" viewBox="0 0 12 12" role="img" aria-label={part.char}><rect x="0.5" y="0.5" width="11" height="11" rx="1.5" /><path d={part.lines} /></svg>{:else}{part.char}{/if}{/each}</span>

<style>
  .op {
    display: inline-block;
    inline-size: 0.95em;
    block-size: 0.95em;
    margin-inline: 0.06em;
    vertical-align: -0.08em;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.3;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .op rect {
    opacity: 0.7;
  }
</style>
