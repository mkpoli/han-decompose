/** Reading the bytes of a release file. */

/** Whether the bytes begin a gzip stream. */
export const isGzip = (bytes: Uint8Array): boolean => bytes.length > 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;

/** The bytes decompressed when they are gzip; as they are otherwise. */
export async function gunzipIfNeeded(bytes: Uint8Array): Promise<Uint8Array> {
  if (!isGzip(bytes)) return bytes;
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function gunzipText(bytes: Uint8Array): Promise<string> {
  return new TextDecoder().decode(await gunzipIfNeeded(bytes));
}

/** The lines of a gzip or plain text stream, read as they arrive. */
export async function* streamLines(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const first = await reader.read();
  const rest = new ReadableStream<Uint8Array>({
    start(controller) {
      if (!first.done) controller.enqueue(first.value);
    },
    async pull(controller) {
      if (first.done) return controller.close();
      const next = await reader.read();
      if (next.done) controller.close();
      else controller.enqueue(next.value);
    },
  });
  const plain = !first.done && isGzip(first.value) ? rest.pipeThrough(new DecompressionStream("gzip") as unknown as ReadableWritablePair<Uint8Array, Uint8Array>) : rest;
  const text = plain.pipeThrough(new TextDecoderStream() as unknown as ReadableWritablePair<string, Uint8Array>).getReader();
  let held = "";
  for (;;) {
    const { done, value } = await text.read();
    if (done) break;
    held += value;
    let at = held.indexOf("\n");
    let from = 0;
    while (at >= 0) {
      yield held.slice(from, at);
      from = at + 1;
      at = held.indexOf("\n", from);
    }
    held = held.slice(from);
  }
  if (held) yield held;
}
