<script lang="ts">
  // A description sequence as text, set in a face that has the ideographic description characters.
  let { text }: { text: string } = $props();
</script>

<span class="ids">{text}</span>

<style>
  .ids {
    font-family: var(--ids-font);
  }
</style>
