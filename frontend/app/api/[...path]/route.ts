import applicationConfig from "../../../../config/application.json";
import { loadCloudSettings } from "@/lib/server/cloudSettings";

export const maxDuration = 240;

export function configuredBackend(): string {
  return process.env.BACKEND_INTERNAL_URL?.trim() || applicationConfig.backend.internalUrl;
}

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some((segment) => !/^[A-Za-z0-9_.-]+$/.test(segment) || segment === "." || segment === "..")) {
    return Response.json({ error: { message: "Invalid API path" } }, { status: 400 });
  }
  let backend = configuredBackend().replace(/\/$/, "");
  let cloud;
  try {
    cloud = loadCloudSettings();
    if (cloud) {
      const { ensureController } = await import("@/lib/server/controller");
      backend = (await ensureController(cloud)).origin;
    }
  } catch {
    return Response.json({ error: { message: "Cloud backend unavailable. Check private configuration and free Sandbox quota." } }, { status: 503 });
  }
  const incoming = new URL(request.url);
  const target = `${backend}/api/${path.join("/")}${incoming.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("x-studio-control");
  if (cloud) {
    headers.set("x-studio-control", cloud.controlSecret);
    headers.delete("x-companion-admin-token");
    if (path[0] === "companions" && (path[1] === "pair-codes" || request.method === "DELETE")) {
      headers.set("x-companion-admin-token", cloud.companionToken);
    }
  }
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const response = await fetch(target, { method: request.method, headers, body, cache: "no-store", redirect: "manual" });
  return new Response(response.body, { status: response.status, headers: response.headers });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
