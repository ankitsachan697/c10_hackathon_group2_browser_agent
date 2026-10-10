import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import ProjectsPage from "@/app/projects/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "DELETE") return new Response(JSON.stringify({ data: { deleted: true } }));
    if (url.includes("deletion-impact")) return new Response(JSON.stringify({ data: { journeys: 2, schedules: 1, runs: 4, artifacts: 6 } }));
    if (url.endsWith("/run")) return new Response(JSON.stringify({ data: [] }));
    return new Response(JSON.stringify({ data: [{ id: "p1", name: "Storefront", description: "Checkout paths" }], meta: { total: 1 } }));
  }));
});

test("searches projects and exposes run and confirmed delete actions", async () => {
  render(<ProjectsPage />);
  expect(await screen.findByText("Storefront")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("Search projects")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  fireEvent.click(screen.getByRole("button", { name: "Run now" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/run"), expect.anything()));
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(await screen.findByRole("dialog")).toHaveTextContent("2 journeys");
  fireEvent.click(screen.getByRole("button", { name: "Delete project" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/projects/p1"), expect.objectContaining({ method: "DELETE" })));
});
