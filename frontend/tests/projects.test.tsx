import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import ProjectsPage from "@/app/projects/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "DELETE") return new Response(JSON.stringify({ data: { deleted: true } }));
    if (url.includes("deletion-impact")) return new Response(JSON.stringify({ data: { journeys: 2, schedules: 1, runs: 4, artifacts: 6 } }));
    if (url.endsWith("/api/journeys/j1/run")) return new Response(JSON.stringify({ data: { id: "run-current", journey_id: "j1", project_id: "p1", status: "PASSED", trigger_source: "ON_DEMAND", attempt_count: 1, created_at: "2026-10-11T10:00:00Z" } }));
    if (url.endsWith("/run")) return new Response(JSON.stringify({ data: [] }));
    if (url.endsWith("/rerun")) return new Response(JSON.stringify({ data: { id: "run-new", journey_id: "j1", project_id: "p1", status: "PASSED", trigger_source: "RERUN_SNAPSHOT", attempt_count: 1, created_at: "2026-10-11T10:00:00Z" } }));
    if (url.endsWith("/api/journeys")) return new Response(JSON.stringify({ data: [
      { id: "j1", project_id: "p1", name: "Saved checkout", target_url: "https://shop.example", script: "print('saved')", active: 1 },
      { id: "j2", project_id: "p2", name: "Other project journey", target_url: "https://other.example", script: "print('other')", active: 1 },
    ] }));
    if (url.endsWith("/api/runs")) return new Response(JSON.stringify({ data: [
      { id: "run-old", journey_id: "j1", project_id: "p1", status: "PASSED", trigger_source: "ON_DEMAND", attempt_count: 1, script_version: 2, created_at: "2026-10-10T10:00:00Z" },
      { id: "run-other", journey_id: "j2", project_id: "p2", status: "FAILED", trigger_source: "ON_DEMAND", attempt_count: 1, created_at: "2026-10-10T10:00:00Z" },
    ] }));
    return new Response(JSON.stringify({ data: [{ id: "p1", name: "Storefront", description: "Checkout paths" }], meta: { total: 1 } }));
  }));
});

test("searches projects and exposes run and confirmed delete actions", async () => {
  render(<ProjectsPage />);
  expect(await screen.findByText("Storefront")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("Search projects")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Run now" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/run"), expect.anything()));
  const workspace = await screen.findByRole("dialog", { name: "Storefront" });
  fireEvent.click(within(workspace).getByRole("button", { name: "Close project" }));
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
  expect(await screen.findByRole("dialog", { name: "Delete Storefront?" })).toHaveTextContent("2 journeys");
  fireEvent.click(screen.getByRole("button", { name: "Delete project" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/projects/p1"), expect.objectContaining({ method: "DELETE" })));
});

test("clicking a project row opens only its journeys and run history", async () => {
  render(<ProjectsPage />);
  fireEvent.click(await screen.findByText("Checkout paths"));
  const drawer = await screen.findByRole("dialog", { name: "Storefront" });
  expect(await within(drawer).findByText("Saved checkout")).toBeVisible();
  expect(within(drawer).queryByText("Other project journey")).not.toBeInTheDocument();
  fireEvent.click(within(drawer).getByRole("tab", { name: /Run history/ }));
  expect(await within(drawer).findByRole("link", { name: /Open run run-old/ })).toHaveAttribute("href", "/runs/run-old");
  expect(within(drawer).queryByText("run-other")).not.toBeInTheDocument();
});

test("historic rerun executes its saved snapshot and exposes the resulting run", async () => {
  render(<ProjectsPage />);
  fireEvent.click(await screen.findByText("Checkout paths"));
  const drawer = await screen.findByRole("dialog", { name: "Storefront" });
  await within(drawer).findByText("Saved checkout");
  fireEvent.click(within(drawer).getByRole("tab", { name: /Run history/ }));
  fireEvent.click(within(drawer).getByRole("button", { name: /Rerun this version/ }));
  expect(await within(drawer).findByRole("link", { name: "Open latest run" })).toHaveAttribute("href", "/runs/run-new");
  expect(fetch).toHaveBeenCalledWith("/api/runs/run-old/rerun", expect.objectContaining({ method: "POST", body: JSON.stringify({ mode: "snapshot" }) }));
  expect(fetch).not.toHaveBeenCalledWith(expect.stringContaining("generate"), expect.anything());
});

test("project menu can open history without accidentally opening the row", async () => {
  render(<ProjectsPage />);
  await screen.findByText("Storefront");
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("menuitem", { name: "View run history" }));
  const drawer = await screen.findByRole("dialog", { name: "Storefront" });
  expect(within(drawer).getByRole("tab", { name: /Run history/ })).toHaveAttribute("aria-selected", "true");
});

test("a journey runs the current saved script without generating a new one", async () => {
  render(<ProjectsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Open project Storefront" }));
  const drawer = await screen.findByRole("dialog", { name: "Storefront" });
  fireEvent.click(await within(drawer).findByRole("button", { name: "Run saved script" }));
  expect(await within(drawer).findByRole("link", { name: "Open latest run" })).toHaveAttribute("href", "/runs/run-current");
  expect(fetch).toHaveBeenCalledWith("/api/journeys/j1/run", expect.objectContaining({ method: "POST" }));
});

test("failed detail loading offers refresh and never displays other project data", async () => {
  render(<ProjectsPage />);
  await screen.findByText("Storefront");
  vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"));
  fireEvent.click(screen.getByRole("button", { name: "Open project Storefront" }));
  const drawer = await screen.findByRole("dialog", { name: "Storefront" });
  expect(await within(drawer).findByRole("alert")).toHaveTextContent("Backend is unavailable");
  expect(within(drawer).getByRole("button", { name: "Refresh project" })).toBeEnabled();
  expect(within(drawer).getByRole("button", { name: "Run all journeys" })).toBeDisabled();
});

test("closing the drawer restores focus to the project opener", async () => {
  render(<ProjectsPage />);
  const opener = await screen.findByRole("button", { name: "Open project Storefront" });
  opener.focus(); fireEvent.click(opener);
  await screen.findByRole("dialog", { name: "Storefront" });
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
});
