import { afterEach, expect, test, vi } from "vitest";
import { configuredBackend, GET } from "@/app/api/[...path]/route";

const original = process.env.BACKEND_INTERNAL_URL;
afterEach(() => {
  if (original === undefined) delete process.env.BACKEND_INTERNAL_URL;
  else process.env.BACKEND_INTERNAL_URL = original;
  vi.unstubAllGlobals();
});

test("decoded upstream JSON drops compression metadata and browser cookies", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"data":[]}', {headers:{"content-type":"application/json","content-encoding":"br","content-length":"9","transfer-encoding":"chunked"}}));
  vi.stubGlobal("fetch", fetch);
  const response = await GET(new Request("http://localhost/api/operations/one/events", {headers:{cookie:"private-browser-cookie", "accept-encoding":"br", "Idempotency-Key":"synthetic-key"}}), {params:Promise.resolve({path:["operations","one","events"]})});
  expect(response.headers.has("content-encoding")).toBe(false);
  expect(response.headers.has("content-length")).toBe(false);
  expect(response.headers.get("cache-control")).toBe("private, no-store");
  expect(await response.json()).toEqual({data:[]});
  const headers = fetch.mock.calls[0][1].headers as Headers;
  expect(headers.has("cookie")).toBe(false);
  expect(headers.get("accept-encoding")).toBe("identity");
  expect(headers.get("Idempotency-Key")).toBe("synthetic-key");
});

test("empty runtime backend override falls back to tracked configuration", () => {
  process.env.BACKEND_INTERNAL_URL = "  ";
  expect(configuredBackend()).toBe("http://127.0.0.1:8000");
});
