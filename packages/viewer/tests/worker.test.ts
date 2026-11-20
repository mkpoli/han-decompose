import { expect, test } from "bun:test";
import worker from "../server/worker.ts";

const SHELL = '<head><link rel="canonical" href="https://decompose.mkpo.li/"><meta property="og:url" content="https://decompose.mkpo.li/"></head>';
const FILES = new Set(["/robots.txt"]);

const env = {
  ASSETS: {
    async fetch(input: Request | string): Promise<Response> {
      const path = new URL(typeof input === "string" ? input : input.url).pathname;
      if (path === "/index.html") return new Response(SHELL, { headers: { "content-type": "text/html" } });
      return FILES.has(path) ? new Response("file") : new Response("not found", { status: 404 });
    },
  },
};

const get = (path: string): Promise<Response> => worker.fetch(new Request(`https://decompose.mkpo.li${path}`), env);

test("a route answers with the app and its own canonical address", async () => {
  for (const path of ["/", "/skipped", "/skipped/", "/review", "/char/U+5D14", "/component/u:5C71", "/font/noto-sans-cjk-jp@2.004"]) {
    const response = await get(path);
    expect(response.status, path).toBe(200);
    const body = await response.text();
    const canonical = new URL(path.replace(/\/+$/, "") || "/", "https://decompose.mkpo.li").toString();
    expect(body, path).toContain(`<link rel="canonical" href="${canonical}">`);
    expect(body, path).toContain(`<meta property="og:url" content="${canonical}">`);
  }
});

test("a path that is no route answers as the assets do", async () => {
  for (const path of ["/nonsense", "/char/崔", "/skippedfoo", "/a/b"]) expect((await get(path)).status, path).toBe(404);
  expect(await (await get("/robots.txt")).text()).toBe("file");
});
