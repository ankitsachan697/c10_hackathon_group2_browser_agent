import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { RunActivity } from "@/components/runs/RunActivity";

afterEach(() => vi.unstubAllGlobals());
const envelope = (data: unknown) => new Response(JSON.stringify({ data, error: null, meta: {} }));

test("shows observed events in order and asks for events after the last sequence", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    if (String(input).includes("events")) return envelope([
      { seq: 3, source: "playwright", kind: "action.started", payload: { action: "fill", attempt: 1 }, created_at: "2026-10-11T00:00:00Z" },
      { seq: 4, source: "playwright", kind: "action.finished", payload: { action: "fill", attempt: 1 }, created_at: "2026-10-11T00:00:01Z" },
    ]);
    return envelope({ id: "run1", status: "PASSED", attempt_count: 1 });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<RunActivity runId="run1"/>);
  expect(await screen.findByText(/fill started/i)).toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/runs/run1/events?after_seq=0", expect.anything()));
  expect(screen.getByText(/fill finished/i)).toBeInTheDocument();
});
