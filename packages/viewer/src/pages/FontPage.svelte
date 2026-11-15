<script lang="ts">
  import { chainOf, dataUrl, countsOf, fontOf, sourceOf, sourcesOfFont } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import ReleaseGate from "../ui/ReleaseGate.svelte";

  let { id }: { id: string } = $props();

  const STATUSES = ["accepted", "refused", "reviewed-right", "reviewed-wrong"] as const;
</script>

<ReleaseGate>
  {#snippet children(rel)}
    {@const font = fontOf(rel, id)}
    {#if !font}
      <div class="empty-note">{t("font.missing")}</div>
    {:else}
      {@const chain = chainOf(rel, font.id)}
      <div class="page-head">
        <h1>{font.name}</h1>
        <span class="ui-chip mono">{font.version}</span>
        <span class="ui-chip">{font.style}</span>
        {#if chain}<span class="ui-chip" data-variant="accent">{chain}</span>{/if}
      </div>

      <section class="section">
        <dl class="facts">
          <dt>{t("font.id")}</dt><dd class="mono">{font.id}</dd>
          {#if font.nameVersion}<dt>{t("font.nameVersion")}</dt><dd>{font.nameVersion}</dd>{/if}
          <dt>{t("font.licence")}</dt>
          <dd>
            {font.licence}
            {#if font.licenceFile}<a href={dataUrl(`LICENSES/${font.licenceFile}`)} target="_blank" rel="noreferrer">{font.licenceFile}</a>{/if}
          </dd>
          {#if font.licenceEvidence}<dt>{t("font.licenceEvidence")}</dt><dd>{font.licenceEvidence}</dd>{/if}
          <dt>{t("font.copyright")}</dt><dd>{font.copyright}</dd>
          {#if font.reservedNames?.length}<dt>{t("font.reservedNames")}</dt><dd>{font.reservedNames.join(", ")}</dd>{/if}
          <dt>{t("font.url")}</dt><dd><a href={font.url} target="_blank" rel="noreferrer" class="url">{font.url}</a></dd>
          <dt>{t("font.file")}</dt><dd class="mono">{font.file}</dd>
          <dt>{t("font.sha256")}</dt><dd class="mono digest">{font.sha256}</dd>
          {#if font.archive}<dt>{t("font.archive")}</dt><dd class="mono digest">{font.archive.sha256} {font.archive.member}</dd>{/if}
          <dt>{t("font.upem")}</dt><dd class="num">{n(font.upem)}</dd>
          {#if font.instance}<dt>{t("font.instance")}</dt><dd class="mono">{Object.entries(font.instance).map(([axis, value]) => `${axis} ${value}`).join(", ")}</dd>{/if}
          {#if font.index !== undefined}<dt>{t("font.index")}</dt><dd class="num">{font.index}</dd>{/if}
        </dl>
      </section>

      <section class="section">
        <h2>{t("font.counts")}</h2>
        <div class="scroll-x">
          <table class="data">
            <thead>
              <tr>
                <th>{t("count.source")}</th>
                <th class="num">{t("count.readings")}</th>
                {#each STATUSES as status (status)}<th class="num">{t(`status.${status}`)}</th>{/each}
                <th class="num">{t("count.components")}</th>
                <th class="num">{t("count.skipped")}</th>
              </tr>
            </thead>
            <tbody>
              {#each sourcesOfFont(rel, font.id) as source (source)}
                {@const c = countsOf(rel, font.id, source)}
                <tr>
                  <td title={sourceOf(rel, source)?.name}>{source}</td>
                  <td class="num">{n(c.readings)}</td>
                  {#each STATUSES as status (status)}<td class="num">{n(c.cuts[status] ?? 0)}</td>{/each}
                  <td class="num">{n(c.components)}</td>
                  <td class="num">{n(c.skipped)}</td>
                </tr>
              {:else}
                <tr><td colspan="8" class="muted">{t("font.noCounts")}</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}
  {/snippet}
</ReleaseGate>

<style>
  .facts {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: var(--ui-space-sm) var(--ui-space-xl);
    margin: 0;
    padding: var(--ui-space-xl);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
  }
  .facts dt {
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-sm);
  }
  .facts dd {
    margin: 0;
    min-inline-size: 0;
    overflow-wrap: anywhere;
  }
  .digest {
    font-size: var(--ui-text-xs);
  }
  .url {
    word-break: break-all;
  }
  @media (max-width: 599px) {
    .facts {
      grid-template-columns: minmax(0, 1fr);
      gap: var(--ui-space-3xs);
    }
    .facts dd {
      margin-block-end: var(--ui-space-sm);
    }
  }
</style>
