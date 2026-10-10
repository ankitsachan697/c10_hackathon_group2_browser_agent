import { afterEach, expect, test } from "vitest";
import { configuredBackend } from "@/app/api/[...path]/route";

const original = process.env.BACKEND_INTERNAL_URL;
afterEach(() => {
  if (original === undefined) delete process.env.BACKEND_INTERNAL_URL;
  else process.env.BACKEND_INTERNAL_URL = original;
});

test("empty runtime backend override falls back to tracked configuration", () => {
  process.env.BACKEND_INTERNAL_URL = "  ";
  expect(configuredBackend()).toBe("http://127.0.0.1:8000");
});
