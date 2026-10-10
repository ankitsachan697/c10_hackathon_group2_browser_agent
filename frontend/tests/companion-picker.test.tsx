import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { CompanionPicker } from "@/components/browser/CompanionPicker";

afterEach(() => vi.unstubAllGlobals());
const envelope = (data: unknown) => new Response(JSON.stringify({ data, error: null, meta: {} }));

test("hosted headed is disabled until a device is online", async () => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => envelope(
    String(input).endsWith("capabilities") ? { location: "hosted", headed_supported: false, reason: "Pair a local browser first" } : []
  )));
  render(<CompanionPicker mode="headless" onModeChange={() => undefined} companionId="" onCompanionChange={() => undefined}/>);
  expect(await screen.findByText("Pair a local browser first")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Watch in browser/ })).toBeDisabled();
});

test("online device can be selected without exposing its credential", async () => {
  const onModeChange = vi.fn();
  const onCompanionChange = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => envelope(
    String(input).endsWith("capabilities") ? { location: "hosted", headed_supported: true } : [{ id: "device-1", name: "Demo laptop", online: true }]
  )));
  render(<CompanionPicker mode="headless" onModeChange={onModeChange} companionId="" onCompanionChange={onCompanionChange}/>);
  const headed = await screen.findByRole("radio", { name: /Watch in browser/ });
  fireEvent.click(headed);
  expect(onModeChange).toHaveBeenCalledWith("headed");
  expect(onCompanionChange).toHaveBeenCalledWith("device-1");
  expect(screen.queryByText(/credential/i)).not.toBeInTheDocument();
});
