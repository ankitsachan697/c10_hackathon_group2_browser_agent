import { readFileSync } from "node:fs";
import { join } from "node:path";

function configuredBackend(): string {
  if (process.env.BACKEND_INTERNAL_URL) return process.env.BACKEND_INTERNAL_URL;
  for (const candidate of [join(process.cwd(), "config/application.json"), join(process.cwd(), "../config/application.json")]) {
    try {
      const config = JSON.parse(readFileSync(candidate, "utf8")) as { backend: { internalUrl: string } };
      if (config.backend?.internalUrl) return config.backend.internalUrl;
    } catch { /* try the next deployment layout */ }
  }
  throw new Error("Backend internal URL is not configured");
}

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const backend = configuredBackend().replace(/\/$/, "");
  const incoming = new URL(request.url);
  const target = `${backend}/api/${path.join("/")}${incoming.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const response = await fetch(target, { method: request.method, headers, body, cache: "no-store" });
  return new Response(response.body, { status: response.status, headers: response.headers });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
