// Places the pinned data release under dist/data for deployment: downloads the release's assets,
// checks the asset list against the pinned digest and every asset against the list, and unpacks
// the archives into the layout of docs/format.md §4.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

type Pin = { repo: string; tag: string; assets: string };

const root = join(import.meta.dir, "..");
const pin: Pin = JSON.parse(readFileSync(join(root, "release.json"), "utf8"));
const out = join(root, "dist", "data");
const base = `https://github.com/${pin.repo}/releases/download/${pin.tag}/`;

const sha256 = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");

async function download(name: string): Promise<Uint8Array> {
  for (let attempt = 1; ; attempt++) {
    let problem: string;
    try {
      const response = await fetch(base + encodeURIComponent(name));
      if (response.ok) return new Uint8Array(await response.arrayBuffer());
      problem = `HTTP ${response.status}`;
    } catch (error) {
      problem = String(error);
    }
    if (attempt === 4) throw new Error(`${name}: ${problem}`);
    await Bun.sleep(3000 * attempt);
  }
}

const list = await download("SHA256SUMS.assets");
if (sha256(list) !== pin.assets) throw new Error(`SHA256SUMS.assets of ${pin.tag} does not match release.json`);

const rows = new TextDecoder()
  .decode(list)
  .split("\n")
  .filter(Boolean)
  .map((line) => {
    const [digest, name] = line.split(/ {2}/);
    if (!digest || !name || name.includes("/")) throw new Error(`bad line in SHA256SUMS.assets: ${line}`);
    return { digest, name };
  });

mkdirSync(out, { recursive: true });
const queue = rows.slice();
const worker = async () => {
  for (let row = queue.shift(); row; row = queue.shift()) {
    const bytes = await download(row.name);
    if (sha256(bytes) !== row.digest) throw new Error(`${row.name}: digest mismatch`);
    if (row.name.endsWith(".tar.gz")) {
      const tar = Bun.spawn(["tar", "-xz", "-C", out], { stdin: bytes });
      if ((await tar.exited) !== 0) throw new Error(`${row.name}: tar failed`);
    } else {
      writeFileSync(join(out, row.name), bytes);
    }
  }
};
await Promise.all(Array.from({ length: 6 }, worker));
console.log(`${pin.tag}: ${rows.length} assets placed in dist/data`);
