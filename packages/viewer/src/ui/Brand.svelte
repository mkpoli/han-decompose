<script lang="ts">
  // The mark: a glyph split in two parts, a stem and a pair of boxes, each in its own colour.
  let { size = 28 }: { size?: number } = $props();
</script>

<svg viewBox="0 0 32 32" width={size} height={size} aria-hidden="true">
  <path d="M5 4h12v24H5z" fill="var(--ui-color-accent)" />
  <path d="M20 4h7v10h-7zM20 18h7v10h-7z" fill="var(--hd-node-2)" />
</svg>
