/** Development middleware: the release folder at `/data/` and the verdict endpoints. */
import { execFileSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import type { Plugin } from "vite";
import type { VerdictRow } from "han-decompose";
import { parseTable } from "../src/lib/tsv.ts";
import { readVerdict, stamp, VERDICT_HEADER, verdictLine } from "./verdicts.ts";

const TYPES: Record<string, string> = {
  ".gz": "application/gzip",
  ".json": "application/json; charset=utf-8",
  ".tsv": "text/tab-separated-values; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

type Next = () => void;

function serveRelease(root: string) {
  return (request: IncomingMessage, response: ServerResponse): void => {
    let name: string;
    try {
      name = decodeURIComponent((request.url ?? "").split("?")[0] ?? "").replace(/^\/+/, "");
    } catch {
      response.statusCode = 400;
      response.end("bad path");
      return;
    }
    const file = resolve(root, normalize(name));
    if (!name || (file !== root && !file.startsWith(root + sep)) || !existsSync(file) || !statSync(file).isFile()) {
      response.statusCode = 404;
      response.end("not in the release");
      return;
    }
    // A .gz is sent as the bytes it is, with no content-encoding: the page unpacks it.
    response.setHeader("content-type", TYPES[extname(file)] ?? "application/octet-stream");
    response.setHeader("cache-control", "no-cache");
    response.end(readFileSync(file));
  };
}

function reviewer(): string {
  if (process.env.HD_REVIEWER) return process.env.HD_REVIEWER;
  try {
    return execFileSync("git", ["config", "user.name"], { encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

function body(request: IncomingMessage): Promise<string> {
  return new Promise((done, fail) => {
    const parts: Buffer[] = [];
    let size = 0;
    request.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > 64 * 1024) fail(new Error("too large"));
      else parts.push(chunk);
    });
    request.on("end", () => done(Buffer.concat(parts).toString("utf8")));
    request.on("error", fail);
  });
}

function send(response: ServerResponse, status: number, data: unknown): void {
  response.statusCode = status;
  response.setHeader("content-type", "application/json; charset=utf-8");
  response.end(JSON.stringify(data));
}

function verdictApi(file: string) {
  return async (request: IncomingMessage, response: ServerResponse, next: Next): Promise<void> => {
    const url = (request.url ?? "").split("?")[0];
    if (url === "/api/verdicts" && request.method === "GET") {
      const rows = existsSync(file) ? parseTable(readFileSync(file, "utf8")).rows : [];
      return send(response, 200, rows);
    }
    if (url === "/api/verdict" && request.method === "POST") {
      try {
        const read = readVerdict(JSON.parse(await body(request)));
        if (!read.ok) return send(response, 400, { error: read.error });
        const row: VerdictRow = { ...read.value, reviewer: reviewer(), at: stamp(new Date()) };
        if (!existsSync(file)) {
          mkdirSync(dirname(file), { recursive: true });
          writeFileSync(file, VERDICT_HEADER);
        }
        appendFileSync(file, verdictLine(row));
        return send(response, 200, row);
      } catch (error) {
        return send(response, 400, { error: String(error) });
      }
    }
    next();
  };
}

/** Serves the folder named by `HD_RELEASE` at `/data/`, and in development writes verdicts to `review/verdicts.tsv`. */
export function releasePlugin(repositoryRoot: string): Plugin {
  const folder = process.env.HD_RELEASE ? resolve(process.env.HD_RELEASE) : "";
  return {
    name: "han-decompose-release",
    configureServer(server) {
      if (folder) server.middlewares.use("/data", serveRelease(folder));
      server.middlewares.use(verdictApi(join(repositoryRoot, "review", "verdicts.tsv")));
    },
    configurePreviewServer(server) {
      if (folder) server.middlewares.use("/data", serveRelease(folder));
    },
  };
}
