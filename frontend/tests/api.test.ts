import { afterEach, expect, test, vi } from "vitest";
import { api, ApiError, ApiTransportError, backendUrl } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

test("uses same-origin API paths", async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ data: [{ id: "p1" }], error: null, meta: {} })));
  vi.stubGlobal("fetch", fetchMock);

  await api("/api/projects");

  expect(backendUrl).toBe("");
  expect(fetchMock).toHaveBeenCalledWith("/api/projects", expect.any(Object));
});

test("normalizes a network rejection into a retryable transport error", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));

  await expect(api("/api/projects")).rejects.toMatchObject({
    name: "ApiTransportError", retryable: true, message: "Backend is unavailable. Check that the API service is running, then retry.",
  });
});

test("normalizes a malformed response without exposing its body", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>proxy error</html>", { status: 502 })));

  await expect(api("/api/projects")).rejects.toEqual(expect.any(ApiTransportError));
  await api("/api/projects").catch(error => {
    expect(error.retryable).toBe(true);
    expect(error.message).not.toContain("proxy error");
  });
});

test("preserves structured backend errors", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    data: null, error: { code: "INVALID_PROJECT", message: "Project not found" }, meta: {},
  }), { status: 422 })));

  await expect(api("/api/journeys")).rejects.toMatchObject({ code: "INVALID_PROJECT", message: "Project not found" } satisfies Partial<ApiError>);
});
