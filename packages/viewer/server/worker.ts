/** The deployed viewer: the app's routes answer with the app, anything else that is no file answers 404. */
import { parseRoute } from "../src/lib/router.ts";

interface Env {
  ASSETS: { fetch(request: Request | string): Promise<Response> };
}

const ORIGIN = "https://decompose.mkpo.li";

/** The app shell with its canonical address and og:url set to the path asked for. */
async function shell(env: Env, url: URL): Promise<Response> {
  const asset = await env.ASSETS.fetch(new URL("/index.html", url).toString());
  if (!asset.ok) return asset;
  const canonical = ORIGIN + (url.pathname.replace(/\/+$/, "") || "/");
  return new HTMLRewriter()
    .on('link[rel="canonical"]', { element: (element) => void element.setAttribute("href", canonical) })
    .on('meta[property="og:url"]', { element: (element) => void element.setAttribute("content", canonical) })
    .transform(asset);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (parseRoute(url.pathname).name === "missing") return env.ASSETS.fetch(request);
    return shell(env, url);
  },
};
