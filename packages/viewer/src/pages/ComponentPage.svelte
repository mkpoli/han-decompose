<script lang="ts">
  import { referenceGlyph, relationIndex } from "../lib/components.ts";
  import { chainFonts, fontOf, forms, library, resolveCut, type Release } from "../lib/data.ts";
  import { n, t, tx } from "../lib/i18n.svelte.ts";
  import { componentText, refSelector } from "../lib/ids.ts";
  import { routeHref } from "../lib/router.ts";
  import ComponentLabel from "../ui/ComponentLabel.svelte";
  import CutTile from "../ui/CutTile.svelte";
  import GlyphSvg from "../ui/GlyphSvg.svelte";
  import Help from "../ui/Help.svelte";
  import Icon from "../ui/Icon.svelte";
  import LibrarySection from "../ui/LibrarySection.svelte";
  import Loading from "../ui/Loading.svelte";
  import ReleaseGate from "../ui/ReleaseGate.svelte";
  import Glyph from "../ui/Glyph.svelte";

  let { ref }: { ref: string } = $props();

  async function load(rel: Release) {
    const chains = chainFonts(rel).map((c) => c.chain);
    const [chosen, libraries, relations, reference] = await Promise.all([
      Promise.all(
        chains.map(async (chain) => {
          const form = (await forms(chain))?.forms[ref];
          return { chain, form, resolved: form ? await resolveCut(form.cut) : null };
        }),
      ),
      Promise.all(chains.map(async (chain) => ({ chain, byPlace: (await library(chain))?.library[ref] ?? {} }))),
      relationIndex(rel).then((index) => index.get(ref) ?? []),
      referenceGlyph(rel, ref),
    ]);
    return { chosen: chosen.filter((c) => c.form), libraries: libraries.filter((l) => Object.keys(l.byPlace).length), relations, reference };
  }

  const selector = $derived(refSelector(ref));
</script>

<div class="page-head">
  <h1 class="name"><ComponentLabel {ref} plain /></h1>
  <span class="ui-chip mono">{ref}</span>
  {#if selector}
    <a class="ui-button" href={routeHref({ name: "char", id: selector })}>{t("component.asChar")}<Icon name="arrow-right" size={16} /></a>
  {/if}
  <Help>
    <p>{t("help.component.forms")}</p>
    <p>{t("help.component.library")}</p>
  </Help>
</div>

<ReleaseGate>
  {#snippet children(rel)}
    {#await load(rel)}
      <Loading />
    {:then data}
      {#if !data.chosen.length && !data.libraries.length && !data.relations.length && !data.reference}
        <div class="empty-note">{t("component.none")}</div>
      {/if}

      {#if data.reference}
        <section class="section">
          <h2>{t("component.reference")}</h2>
          <div class="ref">
            <div class="plain"><GlyphSvg glyph={data.reference.glyph} label={componentText(ref)} /></div>
            <div class="stack">
              <a href={routeHref({ name: "font", id: data.reference.font })}>{fontOf(rel, data.reference.font)?.name ?? data.reference.font}</a>
              <span class="mono muted">{data.reference.selector}</span>
            </div>
          </div>
        </section>
      {/if}

      {#if data.chosen.length}
        <section class="section">
          <h2>{t("component.forms")}</h2>
          <div class="forms">
            {#each data.chosen as { chain, form, resolved } (chain)}
              {#if form}
                <div class="ui-card form">
                  <div class="row"><h3>{chain}</h3><span class="ui-chip" data-variant="accent">{t(`basis.${form.basis}`)}</span></div>
                  {#if resolved}<div class="alone"><CutTile {resolved} alone caption={false} /></div>{/if}
                  <dl class="facts">
                    {#if form.hosts !== undefined}<dt>{t("component.hosts")}</dt><dd class="num">{n(form.hosts)}</dd>{/if}
                    {#if resolved}<dt>{t("component.host")}</dt><dd><a href={routeHref({ name: "char", id: resolved.selector })}><Glyph selector={resolved.selector} /> <span class="mono">{resolved.selector}</span></a></dd>{/if}
                  </dl>
                </div>
              {/if}
            {/each}
          </div>
        </section>
      {/if}

      {#if data.libraries.length}
        <section class="section">
          <h2>{t("component.library")}</h2>
          {#each data.libraries as { chain, byPlace } (chain)}
            <LibrarySection {chain} {byPlace} />
          {/each}
        </section>
      {/if}

      {#if data.relations.length}
        <section class="section">
          <h2>{t("component.equivalents")}</h2>
          <div class="scroll-x">
            <table class="data">
              <thead>
                <tr><th>{t("relation.relation")}</th><th>{t("relation.other")}</th><th>{t("relation.basis")}</th><th>{t("relation.tier")}</th><th>{t("count.source")}</th></tr>
              </thead>
              <tbody>
                {#each data.relations as r (r.source + r.component + r.target)}
                  {@const other = r.component === ref ? r.target : r.component}
                  <tr>
                    <td>{tx(`relation.${r.relation}`)}</td>
                    <td><ComponentLabel ref={other} /></td>
                    <td class="basis">{r.basis}</td>
                    <td><span class="ui-chip" data-variant={r.tier === "source" ? "accent" : undefined}>{tx(`tier.${r.tier}`)}</span></td>
                    <td class="mono">{r.source}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>
      {/if}
    {/await}
  {/snippet}
</ReleaseGate>

<style>
  .name {
    font-size: var(--ui-text-2xl);
    line-height: 1;
  }
  .ref {
    display: flex;
    align-items: flex-end;
    gap: var(--ui-space-xl);
  }
  .plain {
    inline-size: 160px;
    padding: var(--ui-space-sm);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-2xs);
  }
  .forms {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr));
    gap: var(--ui-space-xl);
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-md);
  }
  .alone {
    inline-size: min(100%, 160px);
  }
  .facts {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: var(--ui-space-2xs) var(--ui-space-lg);
    margin: 0;
    font-size: var(--ui-text-sm);
  }
  .facts dt {
    color: var(--ui-color-ink-muted);
  }
  .facts dd {
    margin: 0;
  }
  .basis {
    max-inline-size: 60ch;
  }
</style>
