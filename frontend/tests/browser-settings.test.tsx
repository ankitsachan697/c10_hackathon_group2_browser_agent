import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import SettingsPage from "@/app/settings/page";

afterEach(() => vi.unstubAllGlobals());

test("cloud settings distinguish a healthy API from an unavailable worker and show headed setup", async () => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => new Response(JSON.stringify(
    String(input).endsWith("/health") ? { status: "healthy", cloud_mode: true, runner_ready: false, runner_isolation: "pending-cloud-worker", n8n_connected: true, scheduler_ready: false }
      : { data: { headed_supported: false, location: "hosted", reason: "Pair and start a local browser companion first" } }
  ))));
  render(<SettingsPage/>);
  expect(await screen.findByText("Cloud worker pending")).toBeInTheDocument();
  expect(screen.getByText("API ready")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Watch local Chromium" }));
  expect(screen.getByRole("heading", { name: "Install Chromium on your computer" })).toBeInTheDocument();
  expect(screen.getByText(/No public debugging port/)).toBeInTheDocument();
});

test("refresh rechecks real readiness rather than retaining a stale pending state", async () => {
  let ready = false;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => new Response(JSON.stringify(
    String(input).endsWith("/health") ? { status: "healthy", cloud_mode: true, runner_ready: ready, n8n_connected: true }
      : { data: { headed_supported: ready, location: "hosted" } }
  ))));
  render(<SettingsPage/>);
  await screen.findByText("Cloud worker pending");
  ready = true;
  fireEvent.click(screen.getByRole("button", { name: "Refresh readiness" }));
  expect(await screen.findByText("Browser worker ready")).toBeInTheDocument();
});
