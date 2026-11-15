// Client-side routing on the History API: the route follows the address, and a click on a link
// inside the app changes the address without a page load.
import { parseRoute, type Route } from "./router.ts";

export const nav = $state<{ route: Route }>({ route: parseRoute(location.pathname) });

export function go(href: string, replace = false): void {
  const url = new URL(href, location.href);
  if (url.pathname + url.search === location.pathname + location.search) return;
  if (replace) history.replaceState(null, "", href);
  else history.pushState(null, "", href);
  nav.route = parseRoute(url.pathname);
  window.scrollTo(0, 0);
}

export function startRouting(): void {
  addEventListener("popstate", () => {
    nav.route = parseRoute(location.pathname);
  });
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = (event.target as Element | null)?.closest("a");
    if (!link || link.target || link.hasAttribute("download")) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || url.pathname.startsWith("/data/") || url.pathname.startsWith("/api/")) return;
    event.preventDefault();
    go(url.pathname + url.search);
  });
}
