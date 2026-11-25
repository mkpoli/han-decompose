<script lang="ts">
  import AppHeader from "./ui/AppHeader.svelte";
  import { t } from "./lib/i18n.svelte.ts";
  import { nav } from "./lib/nav.svelte.ts";
  import { routeHref } from "./lib/router.ts";
  import Home from "./pages/Home.svelte";
  import CharPage from "./pages/CharPage.svelte";
  import ComponentPage from "./pages/ComponentPage.svelte";
  import FontPage from "./pages/FontPage.svelte";
  import SkippedPage from "./pages/SkippedPage.svelte";
  import ReviewPage from "./pages/ReviewPage.svelte";

  const ORIGIN = "https://decompose.mkpo.li";
  const route = $derived(nav.route);

  $effect(() => {
    const canonical = document.head.querySelector('link[rel="canonical"]');
    const ogUrl = document.head.querySelector('meta[property="og:url"]');
    if (route.name === "missing") {
      canonical?.removeAttribute("href");
      ogUrl?.removeAttribute("content");
      return;
    }
    const url = ORIGIN + routeHref(route);
    canonical?.setAttribute("href", url);
    ogUrl?.setAttribute("content", url);
  });
</script>

<svelte:head><title>{t("app.title")}</title></svelte:head>

<AppHeader />
<main>
  {#if route.name === "home"}
    <Home />
  {:else if route.name === "char"}
    {#key `${route.font ?? ""}/${route.id}`}<CharPage id={route.id} font={route.font} />{/key}
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
