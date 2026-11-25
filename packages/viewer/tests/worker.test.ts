import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import worker from "../server/worker.ts";

const REAL_SHELL = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const HEAD_SHELL = '<head><link rel="canonical" href="https://decompose.mkpo.li/"><meta property="og:url" content="https://decompose.mkpo.li/"></head>';
const FILES = new Set(["/robots.txt"]);

function makeEnv(shell: string) {
  return {
    ASSETS: {
      async fetch(input: Request | string): Promise<Response> {
        const path = new URL(typeof input === "string" ? input : input.url).pathname;
        if (path === "/index.html") return new Response(null, { status: 307, headers: { location: "/" } });
        if (path === "/") return new Response(shell, { headers: { "content-type": "text/html" } });
        return FILES.has(path) ? new Response("file") : new Response("not found", { status: 404 });
      },
    },
  };
}

const get = (path: string, shell = REAL_SHELL, init?: RequestInit): Promise<Response> =>
  worker.fetch(new Request(`https://decompose.mkpo.li${path}`, init), makeEnv(shell));

test("a route answers with the app and its own canonical address", async () => {
  for (const shell of [REAL_SHELL, HEAD_SHELL]) {
    for (const path of ["/", "/skipped", "/skipped/", "/review", "/char/U+5D14", "/component/u:5C71", "/font/noto-sans-cjk-jp@2.004"]) {
      const response = await get(path, shell);
      expect(response.status, path).toBe(200);
      const body = await response.text();
      const canonical = new URL(path.replace(/\/+$/, "") || "/", "https://decompose.mkpo.li").toString();
      expect(body, path).toContain(`<link rel="canonical" href="${canonical}">`);
      expect(body, path).toContain(`<meta property="og:url" content="${canonical}">`);
    }
  }
});

test("lowercase and percent-encoded aliases receive the normalized route canonical", async () => {
  for (const path of ["/char/u+5d14", "/char/U%2B5D14", "/component/u%3A5C71"]) {
    const response = await get(path);
    expect(response.status, path).toBe(200);
    const body = await response.text();
    const expected = path.startsWith("/char/")
      ? "https://decompose.mkpo.li/char/U+5D14"
      : "https://decompose.mkpo.li/component/u:5C71";
    expect(body, path).toContain(`<link rel="canonical" href="${expected}">`);
    expect(body, path).toContain(`<meta property="og:url" content="${expected}">`);
  }
});

test("a HEAD request returns 200 without a body, and writes pass through to assets", async () => {
  const head = await get("/review", REAL_SHELL, { method: "HEAD" });
  expect(head.status).toBe(200);
  expect(await head.text()).toBe("");
  expect((await get("/review", REAL_SHELL, { method: "POST" })).status).toBe(404);
});

test("a path that is no route answers as the assets do", async () => {
  for (const path of ["/nonsense", "/char/崔", "/skippedfoo", "/a/b"]) expect((await get(path)).status, path).toBe(404);
  expect(await (await get("/robots.txt")).text()).toBe("file");
});
