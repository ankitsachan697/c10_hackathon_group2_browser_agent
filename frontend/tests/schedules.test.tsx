import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import SchedulesPage from "@/app/schedules/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
    if (String(input).endsWith("/run")) return new Response(JSON.stringify({ data: { status: "PASSED" } }));
    return new Response(JSON.stringify({ data: [{ id: "s1", journey_id: "j1", local_time: "09:30", timezone: "Asia/Kolkata", enabled: 1, next_run: "2026-10-11T04:00:00Z" }] }));
  }));
});

test("shows daily time timezone enabled state and run now", async () => {
  render(<SchedulesPage />);
  expect(await screen.findByText("Asia/Kolkata")).toBeInTheDocument();
  expect(screen.getByText("09:30")).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Enabled" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Run now" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/schedules/s1/run"), expect.anything()));
});
