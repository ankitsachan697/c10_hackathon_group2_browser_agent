import type { ApiEnvelope } from "./types";

export const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export class ApiError extends Error {
  constructor(public code: string, message: string) { super(message); }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${backendUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = await response.json() as ApiEnvelope<T>;
  if (!response.ok || payload.error) throw new ApiError(payload.error?.code ?? "HTTP_ERROR", payload.error?.message ?? "Request failed");
  return payload.data;
}
