<script lang="ts">
  import { t } from "../lib/i18n.svelte.ts";
</script>

<div class="loading"><span class="ui-spinner" role="status" aria-label={t("state.loading")}></span></div>

<style>
  .loading {
    display: grid;
    place-items: center;
    padding: var(--ui-space-3xl);
  }
</style>
