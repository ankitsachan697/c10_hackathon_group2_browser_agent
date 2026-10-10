import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import RunDetailPage from "@/app/runs/[id]/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    if (init?.method === "DELETE") return new Response(JSON.stringify({ data: { deleted: true } }));
    if (String(input).endsWith("/rerun")) return new Response(JSON.stringify({ data: { id: "run2", status: "PASSED" } }));
    return new Response(JSON.stringify({ data: {
      id: "run1", status: "PASSED_AFTER_REPAIR", trigger_source: "SCHEDULED", attempt_count: 2,
      script_snapshot: "print('old')", repair_patch: "print('healed')", diagnosis_json: JSON.stringify({ root_cause: "Selector changed" }),
      artifacts: [{ id: "a1", kind: "screenshot", storage_path: "run1/failure.png" }], attempts: [{ attempt_number: 1, status: "FAILED" }, { attempt_number: 2, status: "PASSED" }]
    } }));
  }));
});

test("shows audited timeline, evidence tabs, repair and rerun choices", async () => {
  render(<RunDetailPage params={Promise.resolve({ id: "run1" })} />);
  expect(await screen.findByText("Passed after repair")).toBeInTheDocument();
  expect(screen.getByText("Attempt 1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Repair" }));
  expect(screen.getByText("Selector changed")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Run current script" }));
  fireEvent.click(screen.getByRole("button", { name: "Run this version" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/rerun"), expect.objectContaining({ method: "POST" })));
  fireEvent.click(screen.getByRole("button", { name: "Delete run" }));
  expect(await screen.findByRole("dialog")).toBeInTheDocument();
});
