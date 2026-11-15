<script lang="ts">
  import AppHeader from "./ui/AppHeader.svelte";
  import { t } from "./lib/i18n.svelte.ts";
  import { nav } from "./lib/nav.svelte.ts";
  import Home from "./pages/Home.svelte";
  import CharPage from "./pages/CharPage.svelte";
  import ComponentPage from "./pages/ComponentPage.svelte";
  import FontPage from "./pages/FontPage.svelte";
  import SkippedPage from "./pages/SkippedPage.svelte";
  import ReviewPage from "./pages/ReviewPage.svelte";

  const route = $derived(nav.route);
</script>

<svelte:head><title>{t("app.title")}</title></svelte:head>

<AppHeader />
<main>
  {#if route.name === "home"}
    <Home />
  {:else if route.name === "char"}
    {#key route.id}<CharPage id={route.id} />{/key}
  {:else if route.name === "component"}
    {#key route.ref}<ComponentPage ref={route.ref} />{/key}
  {:else if route.name === "font"}
    {#key route.id}<FontPage id={route.id} />{/key}
  {:else if route.name === "skipped"}
    <SkippedPage />
  {:else if route.name === "review"}
    <ReviewPage />
  {:else}
    <div class="empty-note">{t("missing.title")}</div>
  {/if}
</main>
