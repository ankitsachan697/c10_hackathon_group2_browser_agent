import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import JourneyCreatePage from "@/app/journeys/new/page";

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });
const envelope = (data: unknown, status = 200) => new Response(JSON.stringify({ data, error: null, meta: {} }), { status });

test.each(["COMPLETED", "FAILED"])("a restored %s operation does not block a new verification", async status => {
  sessionStorage.setItem("outskill.activeGeneration", "previous");
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => {
    const path = String(input);
    if (path === "/api/operations/previous") return envelope({ id: "previous", status, run_id: null });
    if (path.includes("/events")) return envelope([]);
    return envelope([{ id: "p1", name: "Web", description: "" }]);
  }));
  render(<JourneyCreatePage/>);
  await screen.findByRole("button", { name: "Create another journey" });
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Another login" } });
  fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://example.test/login" } });
  fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "Verify login" } });
  expect(screen.getByRole("button", { name: "Verify & record live" })).toBeEnabled();
});

test("an autofilled password can be submitted without an input event", async () => {
  let submitted: { password?: string } | undefined;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    if (String(input) === "/api/operations/generations") {
      submitted = JSON.parse(String(init?.body));
      return envelope({ id: "new", status: "QUEUED", run_id: null }, 202);
    }
    if (String(input) === "/api/operations/new") return envelope({ id: "new", status: "QUEUED", run_id: null });
    if (String(input).includes("/events")) return envelope([]);
    return envelope([{ id: "p1", name: "Web", description: "" }]);
  }));
  render(<JourneyCreatePage/>);
  await screen.findByRole("option", { name: "Web" });
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Login" } });
  fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://example.test/login" } });
  fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "Verify login" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "student" } });
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(screen.getByLabelText("Password"), "autofilled-secret");
  expect(screen.getByRole("button", { name: "Verify & record live" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Verify & record live" }));
  await waitFor(() => expect(submitted?.password).toBe("autofilled-secret"));
});

test("one form offers project creation, objective, credentials and browser mode", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => envelope([])));
  render(<JourneyCreatePage/>);
  expect(await screen.findByRole("button", { name: "Create first project" })).toBeInTheDocument();
  expect(screen.getByLabelText("Journey name")).toBeInTheDocument();
  expect(screen.getByLabelText("Target URL")).toBeInTheDocument();
  expect(screen.getByLabelText("Objective")).toBeInTheDocument();
  expect(screen.getAllByRole("textbox")[0]).toHaveAccessibleName("Objective");
  expect(screen.getByRole("button", { name: "Verify & record live" })).toBeInTheDocument();
  expect(screen.getByLabelText("Username")).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  expect(screen.getByRole("radio", { name: /Headless/ })).toBeChecked();
  expect(screen.getByRole("radio", { name: /Watch in browser/ })).toBeInTheDocument();
  expect(screen.queryByText("Step 1 of 3")).not.toBeInTheDocument();
});

test("project creation keeps typed journey fields", async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo, init?: RequestInit) => init?.method === "POST"
    ? envelope({ id: "p1", name: "Login coverage", description: "Auth" }, 201) : envelope([]));
  vi.stubGlobal("fetch", fetchMock);
  render(<JourneyCreatePage/>);
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Practice login" } });
  await userEvent.click(await screen.findByRole("button", { name: "Create first project" }));
  await userEvent.type(screen.getByLabelText("Project name"), "Login coverage");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  await waitFor(() => expect(screen.getByLabelText("Project")).toHaveValue("p1"));
  expect(screen.getByLabelText("Journey name")).toHaveValue("Practice login");
});

test("browser-filled password survives edits to another journey field", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => envelope([{ id: "p1", name: "Web", description: "" }])));
  render(<JourneyCreatePage/>);
  await screen.findByRole("option", { name: "Web" });
  const password = screen.getByLabelText("Password") as HTMLInputElement;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(password, "synthetic-secret");
  expect(password).toHaveValue("synthetic-secret");

  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Login" } });

  expect(password).toHaveValue("synthetic-secret");
});

test("submit invokes one generation operation and never puts credentials in objective", async () => {
  let submitted = "";
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const path = String(input);
    if (path === "/api/operations/generations" && init?.method === "POST") {
      submitted = String(init.body);
      return envelope({ id: "op1", status: "QUEUED", run_id: null }, 202);
    }
    if (path === "/api/operations/op1") return envelope({ id: "op1", status: "COMPLETED", run_id: "run1" });
    if (path.startsWith("/api/operations/op1/events")) return envelope([]);
    if (path.startsWith("/api/runs/run1/events")) return envelope([]);
    if (path === "/api/runs/run1") return envelope({ id: "run1", status: "PASSED", attempt_count: 1 });
    return envelope([{ id: "p1", name: "Web", description: "" }]);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<JourneyCreatePage/>);
  await screen.findByRole("option", { name: "Web" });
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Login" } });
  fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://practicetestautomation.com/practice-test-login/" } });
  fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "Validate Logged In Successfully" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "student" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Password123" } });
  await userEvent.click(screen.getByRole("button", { name: "Verify & record live" }));
  await waitFor(() => expect(JSON.parse(submitted).password).toBe("Password123"));
  expect(JSON.parse(submitted).browser_mode).toBe("headless");
  expect(JSON.parse(submitted).objective).not.toContain("Password123");
  expect(fetchMock).toHaveBeenCalledWith("/api/operations/generations", expect.objectContaining({
    method: "POST", headers: expect.objectContaining({ "Idempotency-Key": expect.any(String) }),
  }));
  expect(await screen.findByRole("link", { name: "Open run" })).toHaveAttribute("href", "/runs/run1");
  expect(screen.queryByText("Supply both username and password, or leave both empty.")).not.toBeInTheDocument();
});

test("rejected submission keeps masked credentials available for retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo) => String(input) === "/api/operations/generations"
    ? new Response(JSON.stringify({ data: null, error: { code: "UNAVAILABLE", message: "Try again" }, meta: {} }), { status: 503 })
    : envelope([{ id: "p1", name: "Web", description: "" }])));
  render(<JourneyCreatePage/>);
  await screen.findByRole("option", { name: "Web" });
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Login" } });
  fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://example.test/login" } });
  fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "Log in" } });
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: "student" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "retry-secret" } });
  await userEvent.click(screen.getByRole("button", { name: "Verify & record live" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Try again");
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  expect(screen.getByLabelText("Password")).toHaveValue("retry-secret");
});

test("shows a retryable backend error without an unhandled rejection", async () => {
  let projectCalls = 0;
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    if (String(input) === "/api/projects") {
      projectCalls += 1;
      if (projectCalls === 1) throw new TypeError("Failed to fetch");
      return envelope([{ id: "p1", name: "Recovered", description: "" }]);
    }
    return envelope([]);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<JourneyCreatePage/>);
  expect(await screen.findByText(/Backend is unavailable/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry projects" }));
  expect(await screen.findByRole("option", { name: "Recovered" })).toBeInTheDocument();
});
