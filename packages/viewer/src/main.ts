import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";
import { locale } from "./lib/i18n.svelte.ts";
import { startRouting } from "./lib/nav.svelte.ts";

document.documentElement.lang = locale();
startRouting();
mount(App, { target: document.getElementById("app") as HTMLElement });
