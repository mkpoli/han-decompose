<script lang="ts">
  // System, light or dark, as three segments of one native radio group: arrow keys move the
  // choice and the group is one tab stop.
  import Segmented from './controls/Segmented.svelte'
  import type { Theme } from '../lib/theme.ts'
  let { theme, labels, label, onchange }: { theme: Theme; labels: Record<string, string>; label: string; onchange: (theme: Theme) => void } = $props()
  const options = $derived([
    { value: 'system', icon: 'system', ariaLabel: labels.system, title: labels.system },
    { value: 'light', icon: 'sun', ariaLabel: labels.light, title: labels.light },
    { value: 'dark', icon: 'moon', ariaLabel: labels.dark, title: labels.dark },
  ])
</script>

<Segmented {label} value={theme} options={options} onchange={(value) => onchange(value as Theme)} />
