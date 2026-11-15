import { svelte } from "@sveltejs/vite-plugin-svelte";
import { join } from "node:path";
import { defineConfig } from "vite";
import { releasePlugin } from "./server/release.ts";

// A static app at the root of its host. `HD_RELEASE` names a release folder that development and
// preview serve at /data/; a deployment places the same tree there beside the app.
export default defineConfig({
  root: import.meta.dirname,
  plugins: [svelte(), releasePlugin(join(import.meta.dirname, "..", ".."))],
  build: { outDir: "dist", emptyOutDir: true, target: "es2022" },
});
