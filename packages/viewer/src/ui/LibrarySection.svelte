<script lang="ts">
  // The library cuts of one component in one chain, by place, sortable by evidence and by size.
  import { onMount } from "svelte";
  import { resolveCut, type ResolvedCut } from "../lib/data.ts";
  import { n, t } from "../lib/i18n.svelte.ts";
  import { score, size } from "../lib/reading.ts";
  import CutTile from "./CutTile.svelte";
  import Loading from "./Loading.svelte";
  import Segmented from "./controls/Segmented.svelte";

  let { chain, byPlace }: { chain: string; byPlace: Record<string, string[]> } = $props();

  const PAGE = 48;
  const PLACES = ["L", "C", "R", "T", "M", "B"];

  type Sort = "order" | "evidence" | "size";
  interface Item {
    place: string;
    id: string;
    order: number;
    resolved: ResolvedCut;
  }

  let sort = $state<Sort>("order");
  let loaded = $state.raw<Item[]>([]);
  let loading = $state(true);
  let cursor = $state(0);

  const flat = $derived(Object.entries(byPlace).flatMap(([place, ids]) => ids.map((id, order) => ({ place, id, order }))));

  /** Resolves the next page of cuts, best first, and shows it as it arrives. */
  async function more(): Promise<void> {
    loading = true;
    const slice = flat.slice(cursor, cursor + PAGE);
    cursor += slice.length;
    const got = await Promise.all(slice.map(async (entry) => ({ ...entry, resolved: await resolveCut(entry.id) })));
    loaded = [...loaded, ...got.filter((e): e is Item => e.resolved !== null)];
    loading = false;
  }

  onMount(() => void more());

  function arranged(list: Item[]): Item[] {
    if (sort === "evidence") return [...list].sort((a, b) => (score(b.resolved.cut) ?? -1) - (score(a.resolved.cut) ?? -1));
    if (sort === "size") return [...list].sort((a, b) => size(b.resolved.cut) - size(a.resolved.cut));
    return [...list].sort((a, b) => a.order - b.order);
  }

  const shown = $derived(arranged(loaded));
  const places = $derived([...new Set(shown.map((e) => e.place))].sort((a, b) => placeOrder(a) - placeOrder(b) || a.localeCompare(b)));

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
        }}
      />
    </div>
  </div>
  {#if loading && !loaded.length}
    <Loading />
  {/if}
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
  {#if cursor < flat.length}
    <div class="row">
      <button type="button" class="ui-button" aria-busy={loading} disabled={loading} onclick={() => void more()}>{t("library.more", { count: Math.min(PAGE, flat.length - cursor) })}</button>
    </div>
  {/if}
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
