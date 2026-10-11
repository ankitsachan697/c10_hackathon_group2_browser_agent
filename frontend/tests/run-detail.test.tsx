import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import RunDetailPage from "@/app/runs/[id]/page";
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

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
  expect(screen.getByRole("tab", { name: "Screenshots" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Recording" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Screenshots" }));
  expect(screen.getByRole("img", { name: "failure.png" }).getAttribute("src")).toMatch(/\/api\/artifacts\/a1$/);
  fireEvent.click(screen.getByRole("tab", { name: "Repair" }));
  expect(screen.getByText("Selector changed")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Run current script" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Run this version" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Run this version" }));
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2));
  expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST").map(([, init]) => JSON.parse(String(init?.body)).mode)).toEqual(["current", "snapshot"]);
  fireEvent.click(screen.getByRole("button", { name: "Delete run" }));
  expect(await screen.findByRole("dialog")).toBeInTheDocument();
});

test("a late response from the previous run cannot replace the queued rerun", async () => {
  let finishOld!: (response: Response) => void;
  let oldReads = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    if (init?.method === "POST") return new Response(JSON.stringify({ data: { id: "run-new", status: "QUEUED", attempt_count: 0 } }));
    if (String(input).endsWith("/api/runs/run-old") && ++oldReads > 1) return new Promise<Response>(resolve => { finishOld = resolve; });
    return new Response(JSON.stringify({ data: { id: String(input).endsWith("run-new") ? "run-new" : "run-old", status: "PASSED", attempt_count: 1 } }));
  }));
  render(<RunDetailPage params={Promise.resolve({ id: "run-old" })}/>);
  await screen.findByRole("heading", { name: "Passed" });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1900)); });
  fireEvent.click(screen.getByRole("button", { name: "Run current script" }));
  await waitFor(() => expect(screen.getByText("Run run-new")).toBeInTheDocument());
  await act(async () => { finishOld(new Response(JSON.stringify({ data: { id: "run-old", status: "PASSED" } }))); });
  expect(screen.getByText("Run run-new")).toBeInTheDocument();
});

test("rerun button follows accepted run status until completion instead of reverting after POST", async () => {
  let resolveSubmit!: (response: Response) => void;
  let nextStatus = "QUEUED";
  let poll!: () => void;
  const realInterval = window.setInterval.bind(window);
  vi.spyOn(window, "setInterval").mockImplementation(((callback: () => void, delay: number) => {
    if (delay === 1800) poll = callback;
    return realInterval(callback, delay);
  }) as typeof window.setInterval);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    if (init?.method === "POST") return new Promise<Response>(resolve => { resolveSubmit = resolve; });
    return new Response(JSON.stringify({ data: { id: String(input).endsWith("run-new") ? "run-new" : "run1", status: String(input).endsWith("run-new") ? nextStatus : "PASSED", attempt_count: 1 } }));
  }));
  render(<RunDetailPage params={Promise.resolve({ id: "run1" })}/>);
  const button = await screen.findByRole("button", { name: "Run current script" });
  fireEvent.click(button);
  expect(button).toHaveAttribute("data-execution-state", "STARTING");
  expect(button).toBeDisabled();
  await act(async () => resolveSubmit(new Response(JSON.stringify({ data: { id: "run-new", status: "QUEUED", attempt_count: 0 } }))));
  await waitFor(() => expect(button).toHaveAttribute("data-execution-state", "QUEUED"));
  expect(screen.getByRole("button", { name: "Run this version" })).toBeDisabled();
  for (const state of ["RUNNING", "REPAIRING", "RETRYING", "PASSED_AFTER_REPAIR"]) {
    nextStatus = state;
    await act(async () => poll());
    await waitFor(() => expect(button).toHaveAttribute("data-execution-state", state));
  }
  expect(button).toBeEnabled();
  expect(button).toHaveTextContent("Passed after repair");
  vi.restoreAllMocks();
});
