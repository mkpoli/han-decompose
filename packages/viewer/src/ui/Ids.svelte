<script lang="ts">
  // A description sequence as text. Machines often lack the ideographic description characters, so
  // each is drawn as a small box showing how it divides its operands.
  let { text }: { text: string } = $props();

  // Each operator as the lines that divide a 12-unit box.
  const LINES: Record<string, string> = {
    "⿰": "M6 1v10",
    "⿱": "M1 6h10",
    "⿲": "M4.3 1v10M7.7 1v10",
    "⿳": "M1 4.3h10M1 7.7h10",
    "⿴": "M3.5 3.5h5v5h-5z",
    "⿵": "M3.5 11V3.5h5V11",
    "⿶": "M3.5 1v7.5h5V1",
    "⿷": "M11 3.5H3.5v5H11",
    "⿸": "M11 3.5H3.5V11",
    "⿹": "M1 3.5h7.5V11",
    "⿺": "M3.5 1v7.5H11",
    "⿻": "M1 4.5h7v7M4.5 1v7h7",
    "⿼": "M11 3.5H3.5V11M6 1v3",
    "⿽": "M1 3.5h7.5V11M6 11V8",
    "⿾": "M6 1v10M1 6h10",
    "⿿": "M1 1l10 10M11 1 1 11",
    "〾": "M3 8c2-6 4 2 6-4",
    "㇯": "M11 3.5H3.5V11M6 1v3",
  };
  const parts = $derived([...text].map((char) => ({ char, lines: LINES[char] })));
</script>

<span class="ids han">{#each parts as part, i (i)}{#if part.lines}<svg class="op" viewBox="0 0 12 12" role="img" aria-label={part.char}><rect x="0.5" y="0.5" width="11" height="11" rx="1.5" /><path d={part.lines} /></svg>{:else}{part.char}{/if}{/each}</span>

<style>
  .op {
    display: inline-block;
    inline-size: 0.8em;
    block-size: 0.8em;
    margin-inline: 0.06em;
    vertical-align: -0.08em;
    fill: none;
    stroke: currentColor;
    stroke-width: 1;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .op rect {
    opacity: 0.45;
  }
</style>
