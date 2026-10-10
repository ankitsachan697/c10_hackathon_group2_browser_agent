import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import JourneyCreatePage from "@/app/journeys/new/page";

afterEach(() => vi.unstubAllGlobals());
const envelope = (data: unknown, status = 200) => new Response(JSON.stringify({ data, error: null, meta: {} }), { status });

test("creates and auto-selects the first project without losing journey input", async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo, init?: RequestInit) => {
    if (init?.method === "POST") return envelope({ id: "p1", name: "Login coverage", description: "Auth" }, 201);
    return envelope([]);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<JourneyCreatePage/>);
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Practice login" } });
  await userEvent.click(await screen.findByRole("button", { name: "Create first project" }));
  expect(screen.getByRole("dialog", { name: "Create project" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Project name"), "Login coverage");
  await userEvent.type(screen.getByLabelText("Project description"), "Auth");
  await userEvent.click(screen.getByRole("button", { name: "Create project" }));
  await waitFor(() => expect(screen.getByLabelText("Project")).toHaveValue("p1"));
  expect(screen.getByLabelText("Journey name")).toHaveValue("Practice login");
  expect(fetchMock).toHaveBeenCalledWith("/api/projects", expect.objectContaining({ method: "POST" }));
});

test("offers new project from a populated selector", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => envelope([{ id: "p1", name: "Existing", description: "" }])));
  render(<JourneyCreatePage/>);
  await screen.findByRole("option", { name: "Existing" });
  fireEvent.change(screen.getByLabelText("Project"), { target: { value: "__new__" } });
  expect(screen.getByRole("dialog", { name: "Create project" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create project" })).toBeDisabled();
});

test("keeps credentials separate, masks review, and submits them only in fields", async () => {
  let submitted = "";
  vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo, init?: RequestInit) => {
    if (init?.method === "POST") { submitted = String(init.body); return envelope({ id: "j1", script: "print('generated')" }, 201); }
    return envelope([{ id: "p1", name: "Web", description: "" }]);
  }));
  render(<JourneyCreatePage/>);
  await screen.findByText("Web");
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Login" } });
  fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://practicetestautomation.com/practice-test-login/" } });
  fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "Validate Logged In Successfully" } });
  await userEvent.click(screen.getByRole("button", { name: "Review journey" }));
  await userEvent.type(screen.getByLabelText("Username"), "student");
  await userEvent.type(screen.getByLabelText("Password"), "Password123");
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  await userEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
  await userEvent.click(screen.getByRole("button", { name: "Review journey" }));
  expect(screen.getByText(/••••••••/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Generate and save" }));
  await screen.findByText("Script ready");
  const body = JSON.parse(submitted);
  expect(body.username).toBe("student");
  expect(body.password).toBe("Password123");
  expect(body.objective).not.toContain("student");
  expect(body.objective).not.toContain("Password123");
});

test("recovers project loading after a transport failure", async () => {
  const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch"))
    .mockResolvedValueOnce(envelope([{ id: "p1", name: "Recovered", description: "" }]));
  vi.stubGlobal("fetch", fetchMock);
  render(<JourneyCreatePage/>);
  expect(await screen.findByText("Backend is unavailable. Check that the API service is running, then retry.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry projects" }));
  expect(await screen.findByRole("option", { name: "Recovered" })).toBeInTheDocument();
});
