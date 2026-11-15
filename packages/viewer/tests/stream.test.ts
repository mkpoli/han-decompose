import { expect, test } from "bun:test";
import { streamLines } from "../src/lib/codec.ts";
import { BoundedHeap } from "../src/lib/heap.ts";
import { Lru } from "../src/lib/lru.ts";

const chunked = (text: string, size: number): ReadableStream<Uint8Array> => {
  const bytes = new TextEncoder().encode(text);
  let at = 0;
  return new ReadableStream({
    pull(controller) {
      if (at >= bytes.length) return controller.close();
      controller.enqueue(bytes.slice(at, at + size));
      at += size;
    },
  });
};

const collect = async (stream: ReadableStream<Uint8Array>): Promise<string[]> => {
  const out: string[] = [];
  for await (const line of streamLines(stream)) out.push(line);
  return out;
};

test("lines come out whole however the chunks fall", async () => {
  expect(await collect(chunked("a\tb\n漢字\tc\n\nlast", 3))).toEqual(["a\tb", "漢字\tc", "", "last"]);
});

test("a gzip stream is read as it is unpacked", async () => {
  const gz = chunked("x\ny\nz\n", 100).pipeThrough(new CompressionStream("gzip") as unknown as ReadableWritablePair<Uint8Array, Uint8Array>);
  const bytes = new Uint8Array(await new Response(gz).arrayBuffer());
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += 5) controller.enqueue(bytes.slice(i, i + 5));
      controller.close();
    },
  });
  expect(await collect(stream)).toEqual(["x", "y", "z"]);
});

test("the heap keeps the smallest keys", () => {
  const heap = new BoundedHeap<number>(3, (n) => n);
  for (const n of [9, 4, 7, 1, 8, 2, 6, 3, 5]) heap.push(n);
  expect(heap.sorted()).toEqual([1, 2, 3]);
  expect(heap.size).toBe(3);
});

test("the heap holds fewer items when fewer come", () => {
  const heap = new BoundedHeap<number>(5, (n) => n);
  heap.push(2);
  heap.push(Number.POSITIVE_INFINITY);
  expect(heap.sorted()).toEqual([2, Number.POSITIVE_INFINITY]);
});

test("the cache forgets the entry used longest ago", () => {
  const lru = new Lru<string, number>(2);
  lru.set("a", 1);
  lru.set("b", 2);
  lru.get("a");
  lru.set("c", 3);
  expect(lru.get("b")).toBeUndefined();
  expect(lru.get("a")).toBe(1);
  expect(lru.size).toBe(2);
});
