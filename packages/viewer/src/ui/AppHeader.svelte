<script lang="ts">
  // The page header: the mark and name, the pages, then the language and theme controls. On a phone
  // the pages move into a drawer.
  import { locale, LOCALES, setLocale, t, type Locale } from "../lib/i18n.svelte.ts";
  import { nav } from "../lib/nav.svelte.ts";
  import { routeHref, type Route } from "../lib/router.ts";
  import { applyTheme, storedTheme, type Theme } from "../lib/theme.ts";
  import Brand from "./Brand.svelte";
  import Icon from "./Icon.svelte";
  import MenuSelect from "./MenuSelect.svelte";
  import ThemeSwitch from "./ThemeSwitch.svelte";

  let theme = $state<Theme>(storedTheme());
  let drawer: HTMLDialogElement | null = $state(null);

  const pages: { route: Route; label: () => string; icon: string }[] = [
    { route: { name: "home" }, label: () => t("nav.search"), icon: "search" },
    { route: { name: "skipped" }, label: () => t("nav.skipped"), icon: "list" },
    { route: { name: "review" }, label: () => t("nav.review"), icon: "check" },
  ];
  const current = (route: Route): boolean => {
    const here = nav.route.name;
    if (route.name === "home") return here === "home" || here === "char" || here === "component" || here === "font";
    return here === route.name;
  };

  const choose = (value: string): void => setLocale(value as Locale);
  const closeOnBackdrop = (event: MouseEvent): void => {
    if (event.target === drawer) drawer?.close();
  };
</script>

<header class="bar">
  <a class="brand" href="/" aria-label={t("app.title")}>
    <Brand />
    <span class="name">{t("app.title")}</span>
  </a>
  <nav class="links" aria-label={t("nav.label")}>
    {#each pages as page (page.route.name)}
      <a class="link" href={routeHref(page.route)} aria-current={current(page.route) ? "page" : undefined}>{page.label()}</a>
    {/each}
  </nav>
  <div class="end">
    <MenuSelect
      label={t("nav.language")}
      value={locale()}
      options={LOCALES.map(([value, label]) => ({ value, label }))}
      onchange={choose}
      icon="globe"
      compact
      align="end"
    />
    <ThemeSwitch
      {theme}
      label={t("nav.theme")}
      labels={{ system: t("theme.system"), light: t("theme.light"), dark: t("theme.dark") }}
      onchange={(next) => {
        theme = next;
        applyTheme(next);
      }}
    />
    <button type="button" class="ui-button menu-button" data-size="icon" aria-label={t("nav.menu")} aria-haspopup="dialog" onclick={() => drawer?.showModal()}>
      <Icon name="menu" />
    </button>
  </div>
</header>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog bind:this={drawer} class="drawer" aria-label={t("nav.menu")} onclick={closeOnBackdrop}>
  <div class="sheet">
    <div class="sheet-head">
      <span class="sheet-title"><Brand size={24} />{t("app.title")}</span>
      <button type="button" class="ui-button" data-variant="quiet" data-size="icon" aria-label={t("nav.close")} onclick={() => drawer?.close()}><Icon name="close" /></button>
    </div>
    <nav class="sheet-links" aria-label={t("nav.label")}>
      {#each pages as page (page.route.name)}
        <a class="ui-menu-item" href={routeHref(page.route)} aria-current={current(page.route) ? "page" : undefined} onclick={() => drawer?.close()}>
          <Icon name={page.icon} size={18} />{page.label()}
        </a>
      {/each}
    </nav>
  </div>
</dialog>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: var(--ui-space-xl);
    padding: var(--ui-space-md) var(--ui-space-xl);
    border-block-end: 1px solid var(--ui-color-border);
    background: var(--ui-color-surface);
  }
  .brand {
    display: flex;
    flex: none;
    align-items: center;
    gap: var(--ui-space-sm);
    color: var(--ui-color-ink);
    font-weight: var(--ui-weight-bold);
    font-size: var(--ui-text-lg);
    text-decoration: none;
    white-space: nowrap;
  }
  .links {
    display: flex;
    gap: var(--ui-space-2xs);
  }
  .link {
    padding: var(--ui-space-xs) var(--ui-space-md);
    border-radius: var(--ui-radius-md);
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-md);
    font-weight: var(--ui-weight-medium);
    text-decoration: none;
  }
  .link:hover {
    background: var(--ui-color-surface-hover);
    color: var(--ui-color-ink);
  }
  .link[aria-current="page"] {
    background: var(--ui-color-accent-soft);
    color: var(--ui-color-accent);
  }
  .end {
    display: flex;
    align-items: center;
    gap: var(--ui-space-sm);
    margin-inline-start: auto;
  }
  .menu-button {
    display: none;
  }
  .drawer {
    inline-size: min(320px, calc(100vw - 48px));
    max-inline-size: none;
    block-size: 100dvh;
    max-block-size: none;
    margin: 0;
    padding: 0;
    border: 0;
    border-inline-end: 1px solid var(--ui-color-border);
    background: var(--ui-color-surface);
    color: var(--ui-color-ink);
    box-shadow: var(--ui-shadow-2);
    overflow-y: auto;
  }
  .drawer::backdrop {
    background: var(--ui-color-overlay);
  }
  .sheet {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-md);
    padding: var(--ui-space-md);
  }
  .sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-inline-start: var(--ui-space-sm);
  }
  .sheet-title {
    display: flex;
    align-items: center;
    gap: var(--ui-space-sm);
    font-weight: var(--ui-weight-bold);
  }
  .sheet-links {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  @media (max-width: 719px) {
    .links {
      display: none;
    }
    .menu-button {
      display: inline-flex;
    }
    .bar {
      gap: var(--ui-space-sm);
      padding-inline: var(--ui-space-xl);
    }
  }
  @media (max-width: 479px) {
    .name {
      display: none;
    }
    .end {
      gap: var(--ui-space-xs);
    }
  }
</style>
