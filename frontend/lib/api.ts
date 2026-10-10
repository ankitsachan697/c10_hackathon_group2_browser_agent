import type { ApiEnvelope } from "./types";

export const backendUrl = "";

export class ApiError extends Error {
  constructor(public code: string, message: string) { super(message); this.name = "ApiError"; }
}

export class ApiTransportError extends Error {
  constructor(message: string, public retryable = true) { super(message); this.name = "ApiTransportError"; }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${backendUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiTransportError("Backend is unavailable. Check that the API service is running, then retry.");
  }
  let payload: ApiEnvelope<T>;
  try {
    payload = await response.json() as ApiEnvelope<T>;
  } catch {
    throw new ApiTransportError("Backend returned an unreadable response. Please retry.");
  }
  if (!response.ok || payload.error) throw new ApiError(payload.error?.code ?? "HTTP_ERROR", payload.error?.message ?? "Request failed");
  return payload.data;
}
