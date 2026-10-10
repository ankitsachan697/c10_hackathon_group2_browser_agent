import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import JourneyCreatePage from "@/app/journeys/new/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    if (!init?.method) return new Response(JSON.stringify({ data: [{ id: "p1", name: "Web" }] }));
    return new Response(JSON.stringify({ data: { id: "j1", name: "Login", script: "print('generated')", discovered_steps: ["Open page"] } }), { status: 201 });
  }));
});

test("generation occurs only after explicit review submission", async () => {
  render(<JourneyCreatePage />);
  await screen.findByText("Web");
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("Journey name"), { target: { value: "Login" } });
  fireEvent.change(screen.getByLabelText("Target URL"), { target: { value: "https://app.invalid" } });
  fireEvent.change(screen.getByLabelText("Objective"), { target: { value: "Sign in and verify dashboard" } });
  fireEvent.click(screen.getByRole("button", { name: "Review journey" }));
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Review journey" }));
  fireEvent.click(screen.getByRole("button", { name: "Generate and save" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/journeys/generate"), expect.objectContaining({ method: "POST" })));
  expect(await screen.findByText("Script ready")).toBeInTheDocument();
});
