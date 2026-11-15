<script lang="ts">
  // The library cuts of one component in one chain, by place, sortable by evidence and by size.
  import { resolveCut } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import { score, size } from "../lib/reading.ts";
  import CutTile from "./CutTile.svelte";
  import Loading from "./Loading.svelte";
  import Segmented from "./controls/Segmented.svelte";

  let { chain, byPlace }: { chain: string; byPlace: Record<string, string[]> } = $props();

  const CAP = 500;
  const PAGE = 48;
  const PLACES = ["L", "C", "R", "T", "M", "B"];

  type Sort = "order" | "evidence" | "size";
  let sort = $state<Sort>("order");
  let limit = $state(PAGE);

  const flat = $derived(Object.entries(byPlace).flatMap(([place, ids]) => ids.map((id, order) => ({ place, id, order }))));
  const items = $derived(
    Promise.all(
      flat.slice(0, CAP).map(async (entry) => ({ ...entry, resolved: await resolveCut(entry.id) })),
    ).then((all) => all.filter((e) => e.resolved !== null) as (typeof all[number] & { resolved: NonNullable<(typeof all)[number]["resolved"]> })[]),
  );

  function arranged<T extends { order: number; resolved: { cut: Parameters<typeof score>[0] & Parameters<typeof size>[0] } }>(list: T[]): T[] {
    if (sort === "evidence") return [...list].sort((a, b) => (score(b.resolved.cut) ?? -1) - (score(a.resolved.cut) ?? -1));
    if (sort === "size") return [...list].sort((a, b) => size(b.resolved.cut) - size(a.resolved.cut));
    return [...list].sort((a, b) => a.order - b.order);
  }

  const placeOrder = (place: string): number => {
    const i = PLACES.indexOf(place);
    return i < 0 ? PLACES.length : i;
  };
</script>

<div class="library">
  <div class="toolbar">
    <h3>{chain}</h3>
    <span class="muted num">{n(flat.length)}</span>
    <div class="sort">
      <Segmented
        label={t("library.sort")}
        value={sort}
        options={[
          { value: "order", label: t("library.order") },
          { value: "evidence", label: t("library.evidence") },
          { value: "size", label: t("library.size") },
        ]}
        onchange={(v) => {
          sort = v as Sort;
          limit = PAGE;
        }}
      />
    </div>
  </div>
  {#await items}
    <Loading />
  {:then all}
    {@const shown = arranged(all).slice(0, limit)}
    {@const places = [...new Set(shown.map((e) => e.place))].sort((a, b) => placeOrder(a) - placeOrder(b) || a.localeCompare(b))}
    {#each places as place (place)}
      <div class="place">
        <div class="row"><span class="ui-chip mono">{place}</span><span class="muted num">{n(shown.filter((e) => e.place === place).length)}</span></div>
        <div class="tiles">
          {#each shown.filter((e) => e.place === place) as entry (entry.id)}
            <CutTile resolved={entry.resolved} />
          {/each}
        </div>
      </div>
    {/each}
    {#if limit < all.length}
      <div class="row"><button type="button" class="ui-button" onclick={() => (limit += PAGE)}>{t("library.more", { count: Math.min(PAGE, all.length - limit) })}</button></div>
    {/if}
    {#if flat.length > CAP}<p class="muted">{t("library.capped", { count: CAP })}</p>{/if}
  {/await}
</div>

<style>
  .library {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-lg);
  }
  .sort {
    margin-inline-start: auto;
  }
  .place {
    display: flex;
    flex-direction: column;
    gap: var(--ui-space-sm);
  }
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: var(--ui-space-sm);
  }
  .toolbar {
    align-items: center;
  }
</style>
