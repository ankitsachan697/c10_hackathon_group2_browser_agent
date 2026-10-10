import applicationConfig from "../../../../config/application.json";

function configuredBackend(): string {
  return process.env.BACKEND_INTERNAL_URL ?? applicationConfig.backend.internalUrl;
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
