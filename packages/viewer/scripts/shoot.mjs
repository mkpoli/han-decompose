// Screenshots every route of the viewer at 1360 and 390 px, light and dark, at 2x, and reports
// console errors and horizontal overflow (also at 320 px).
//   bun scripts/shoot.mjs <out-dir> [base-url]
// The viewer must be running with HD_RELEASE set (devrun bun run dev --port N).
import { mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";

const out = process.argv[2];
const base = process.argv[3] ?? process.env.HD_URL ?? "http://localhost:5173";
if (!out) throw new Error("usage: shoot.mjs <out-dir> [base-url]");
mkdirSync(out, { recursive: true });

const executablePath = process.env.CHROMIUM_PATH ?? join(homedir(), ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome");

const routes = [
  ["home", "/"],
  ["char-multi", "/char/U+2866A"],
  ["char-sans", "/char/U+5019"],
  ["char-ext-a", "/char/U+34EA"],
  ["component-bs", "/component/bs:1"],
  ["component-char", "/component/u:4E28"],
  ["font", "/font/noto-sans-cjk-jp@2.004"],
  ["skipped", "/skipped"],
  ["review", "/review"],
  ["missing", "/nowhere"],
];

const browser = await chromium.launch({ executablePath, args: ["--no-sandbox"] });
const problems = [];

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForFunction(() => !document.querySelector(".ui-spinner"), null, { timeout: 20000 }).catch(() => problems.push(`${page.url()}: still loading`));
  await page.waitForTimeout(400);
}

async function visit(page, name, path, label) {
  await page.goto(base + path);
  await settle(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 0) problems.push(`${label} ${name}: ${overflow}px horizontal overflow`);
}

for (const width of [1360, 390]) {
  for (const scheme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: width > 600 ? 900 : 844 }, deviceScaleFactor: 2, colorScheme: scheme });
    const page = await context.newPage();
    const label = `${width}-${scheme}`;
    page.on("console", (m) => m.type() === "error" && problems.push(`${label} console: ${m.text()}`));
    page.on("pageerror", (e) => problems.push(`${label} pageerror: ${e.message}`));
    for (const [name, path] of routes) {
      await visit(page, name, path, label);
      await page.screenshot({ path: join(out, `${name}-${label}.png`), fullPage: true });
    }
    // States that need a gesture.
    await visit(page, "home", "/", label);
    await page.fill("input[type=search]", "𠀇");
    await page.waitForTimeout(500);
    await page.screenshot({ path: join(out, `home-search-${label}.png`) });
    await page.goto(base + "/char/U+5019");
    await settle(page);
    const hover = page.locator(".cut").first();
    await hover.hover();
    await page.waitForTimeout(250);
    await page.screenshot({ path: join(out, `char-hover-${label}.png`), fullPage: true });
    await page.locator("button[aria-haspopup=menu]").first().click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: join(out, `menu-${label}.png`) });
    await page.keyboard.press("Escape");
    if (width < 600) {
      await page.locator(".menu-button").click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: join(out, `drawer-${label}.png`) });
    } else {
      await page.goto(base + "/skipped");
      await settle(page);
      await page.locator(".help").first().click();
      await page.waitForTimeout(200);
      await page.screenshot({ path: join(out, `help-${label}.png`) });
    }
    await context.close();
  }
}

for (const scheme of ["light", "dark"]) {
  const context = await browser.newContext({ viewport: { width: 320, height: 640 }, deviceScaleFactor: 2, colorScheme: scheme });
  const page = await context.newPage();
  page.on("console", (m) => m.type() === "error" && problems.push(`320-${scheme} console: ${m.text()}`));
  for (const [name, path] of routes) {
    await visit(page, name, path, `320-${scheme}`);
    if (name === "home" || name === "char-sans" || name === "review") await page.screenshot({ path: join(out, `${name}-320-${scheme}.png`), fullPage: true });
  }
  await context.close();
}

await browser.close();
console.log(problems.length ? problems.join("\n") : "no console errors, no horizontal overflow");
process.exitCode = problems.length ? 1 : 0;
