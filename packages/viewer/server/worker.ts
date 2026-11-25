/** The deployed viewer: the app's routes answer with the app, anything else that is no file answers 404. */
import { parseRoute } from "../src/lib/router.ts";

interface Env {
  ASSETS: { fetch(request: Request | string): Promise<Response> };
}

const ORIGIN = "https://decompose.mkpo.li";
const escapeAttr = (value: string): string =>
  value.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] ?? ch);

/** The app shell with its canonical address and og:url set to the path asked for. */
async function shell(env: Env, url: URL, headOnly: boolean): Promise<Response> {
  const asset = await env.ASSETS.fetch(new URL("/", url).toString());
  if (!asset.ok) return asset;
  const canonical = ORIGIN + (url.pathname.replace(/\/+$/, "") || "/");
  let hasCanonical = false;
  let hasOgUrl = false;
  const rewritten = new HTMLRewriter()
    .on('link[rel="canonical"]', {
      element: (element) => {
        hasCanonical = true;
        element.setAttribute("href", canonical);
      },
    })
    .on('meta[property="og:url"]', {
      element: (element) => {
        hasOgUrl = true;
        element.setAttribute("content", canonical);
      },
    })
    .on("head", {
      element: (element) => {
        element.onEndTag((end) => {
          const safe = escapeAttr(canonical);
          if (!hasCanonical) end.before(`<link rel="canonical" href="${safe}">`, { html: true });
          if (!hasOgUrl) end.before(`<meta property="og:url" content="${safe}">`, { html: true });
        });
      },
    })
    .transform(asset);
  if (!headOnly) return rewritten;
  const headers = new Headers(rewritten.headers);
  headers.delete("content-length");
  return new Response(null, { status: rewritten.status, headers });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") return env.ASSETS.fetch(request);
    const url = new URL(request.url);
    if (parseRoute(url.pathname).name === "missing") return env.ASSETS.fetch(request);
    return shell(env, url, request.method === "HEAD");
  },
};
