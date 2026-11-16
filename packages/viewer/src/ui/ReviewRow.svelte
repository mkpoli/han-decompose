<script lang="ts">
  // One cut of the review queue: the host with its pieces one colour each, the cut in the host, the
  // part alone and the reference glyph, then the verdict.
  import type { VerdictRow } from "../lib/format1";
  import { referenceGlyph } from "../lib/components.ts";
  import { resolveCut, type Release } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import { boxViewBox } from "../lib/path.ts";
  import { charHref } from "../lib/router.ts";
  import { nodeColour, nodeIndex, pathKey } from "../lib/reading.ts";
  import ComponentLabel from "./ComponentLabel.svelte";
  import GlyphSvg from "./GlyphSvg.svelte";
  import Icon from "./Icon.svelte";

  let {
    rel,
    row,
    selected,
    verdict,
    editable,
    onselect,
    onverdict,
  }: {
    rel: Release;
    row: Record<string, string>;
    selected: boolean;
    verdict: VerdictRow["verdict"] | null;
    editable: boolean;
    onselect: () => void;
    onverdict: (verdict: VerdictRow["verdict"]) => void;
  } = $props();

  const resolved = $derived(resolveCut(row.cut_id ?? ""));
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<article class="review" class:selected aria-current={selected ? "true" : undefined} id={`cut-${row.sig}-${row.cut_id}`} onclick={onselect}>
  {#await resolved}
    <div class="loading"><span class="ui-spinner" role="status" aria-label={t("state.loading")}></span></div>
  {:then r}
    {#if r?.glyph}
      {@const cut = r.cut}
      {@const colour = nodeColour(nodeIndex(r.reading).get(pathKey(cut.path)) ?? 0)}
      <div class="panels">
        <figure>
          <GlyphSvg glyph={r.glyph} base="none" paints={r.glyph.pieces.map((contours, i) => ({ id: `p${i}`, contours, colour: nodeColour(i) }))} label={t("review.host")} />
          <figcaption>{t("review.host")}</figcaption>
        </figure>
        <figure>
          <GlyphSvg glyph={r.glyph} base="faint" paints={[{ id: cut.id, contours: cut.contours, colour }]} label={t("review.cut")} />
          <figcaption>{t("review.cut")}</figcaption>
        </figure>
        <figure>
          <GlyphSvg glyph={r.glyph} viewBox={boxViewBox(cut.box)} base="none" paints={[{ id: cut.id, contours: cut.contours }]} label={t("review.part")} />
          <figcaption>{t("review.part")}</figcaption>
        </figure>
        {#await referenceGlyph(rel, cut.component) then ref}
          {#if ref}
            <figure>
              <GlyphSvg glyph={ref.glyph} label={t("review.reference")} />
              <figcaption>{t("review.reference")}</figcaption>
            </figure>
          {/if}
        {/await}
      </div>
      <div class="info">
        <div class="row">
          <span class="component"><ComponentLabel ref={cut.component} text={cut.text} /></span>
          {#if cut.place}<span class="ui-chip mono">{cut.place}</span>{/if}
          <span class="ui-chip">{r.reading.method.name}</span>
          {#if verdict}<span class="ui-chip" data-variant={verdict === "right" ? "accent" : "danger"}>{t(`verdict.${verdict}`)}</span>{/if}
        </div>
        <div class="row muted num">
          {#if cut.evidence?.fit !== undefined}<span>{t("evidence.fit")} {n(cut.evidence.fit)}</span>{/if}
          {#if cut.evidence?.match !== undefined}<span>{t("evidence.match")} {n(cut.evidence.match)}</span>{/if}
          {#if cut.evidence?.margin !== undefined}<span>{t("evidence.margin")} {n(cut.evidence.margin)}</span>{/if}
          {#if cut.evidence?.reference !== undefined}<span>{t("evidence.reference")} {n(cut.evidence.reference)}</span>{/if}
        </div>
        <a class="id mono muted" href={charHref(r.selector, r.font)}>{cut.id}</a>
        {#if editable}
          <div class="row">
            <button type="button" class="ui-button" data-variant="primary" aria-pressed={verdict === "right"} onclick={(event) => { event.stopPropagation(); onverdict("right"); }}>
              <Icon name="check" size={16} />{t("verdict.right")} <kbd>R</kbd>
            </button>
            <button type="button" class="ui-button" data-variant="danger" aria-pressed={verdict === "wrong"} onclick={(event) => { event.stopPropagation(); onverdict("wrong"); }}>
              <Icon name="close" size={16} />{t("verdict.wrong")} <kbd>W</kbd>
            </button>
          </div>
        {/if}
      </div>
    {:else}
      <div class="info"><span class="mono muted">{row.cut_id}</span><span class="muted">{t("review.unresolved")}</span></div>
    {/if}
  {/await}
</article>

<style>
  .review {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--ui-space-lg);
    padding: var(--ui-space-lg);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-color-surface);
    scroll-margin-block: var(--ui-space-xl);
  }
  .review.selected {
    border-color: var(--ui-color-accent);
    box-shadow: 0 0 0 1px var(--ui-color-accent);
  }
  .panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(84px, 120px));
    gap: var(--ui-space-md);
    color: var(--ui-color-ink);
  }
  figure {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-2xs);
    padding: var(--ui-space-xs);
    border: 1px solid var(--ui-color-border);
    border-radius: var(--ui-radius-md);
  }
  figcaption {
    color: var(--ui-color-ink-muted);
    font-size: var(--ui-text-xs);
    text-align: center;
  }
  .info {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-sm);
    min-inline-size: 0;
  }
  .component {
    font-size: var(--ui-text-xl);
  }
  .id {
    font-size: var(--ui-text-2xs);
    overflow-wrap: anywhere;
    text-decoration: none;
  }
  kbd {
    padding: 0 var(--ui-space-xs);
    border: 1px solid currentColor;
    border-radius: var(--ui-radius-xs);
    font-family: var(--ui-font-mono);
    font-size: var(--ui-text-2xs);
    opacity: 0.8;
  }
  .loading {
    display: grid;
    place-items: center;
    min-block-size: 120px;
  }
</style>
