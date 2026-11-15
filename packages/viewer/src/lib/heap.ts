/** Keeps the `limit` items with the smallest keys out of any number pushed, in a max-heap. */
export class BoundedHeap<T> {
  private readonly items: T[] = [];

  constructor(
    private readonly limit: number,
    private readonly key: (item: T) => number,
  ) {}

  get size(): number {
    return this.items.length;
  }

  push(item: T): void {
    const items = this.items;
    if (items.length < this.limit) {
      items.push(item);
      this.up(items.length - 1);
    } else if (items.length > 0 && this.key(item) < this.key(items[0] as T)) {
      items[0] = item;
      this.down(0);
    }
  }

  /** The kept items, smallest key first. */
  sorted(): T[] {
    return [...this.items].sort((a, b) => this.key(a) - this.key(b));
  }

  private up(at: number): void {
    const items = this.items;
    while (at > 0) {
      const parent = (at - 1) >> 1;
      if (this.key(items[parent] as T) >= this.key(items[at] as T)) break;
      [items[parent], items[at]] = [items[at] as T, items[parent] as T];
      at = parent;
    }
  }

  private down(at: number): void {
    const items = this.items;
    for (;;) {
      let largest = at;
      for (const child of [2 * at + 1, 2 * at + 2]) {
        if (child < items.length && this.key(items[child] as T) > this.key(items[largest] as T)) largest = child;
      }
      if (largest === at) return;
      [items[largest], items[at]] = [items[at] as T, items[largest] as T];
      at = largest;
    }
  }
}
