import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { AppShell } from "@/components/shell/AppShell";

vi.mock("next/navigation", () => ({ usePathname: () => "/projects" }));

beforeEach(() => vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); })));

test("renders branded navigation and service health", () => {
  render(<AppShell><div>Workspace</div></AppShell>);
  expect(screen.getByAltText("Outskill")).toBeInTheDocument();
  expect(screen.getByText("Group2")).toBeInTheDocument();
  expect(screen.getByRole("navigation")).toHaveTextContent("Demo lab");
  expect(screen.getByRole("navigation")).toHaveTextContent("Overview");
  expect(screen.getByRole("navigation")).toHaveTextContent("Projects");
  expect(screen.getByText("Runner")).toBeInTheDocument();
  expect(screen.getByText("Workspace")).toBeInTheDocument();
});

test("labels unavailable services without throwing", async () => {
  render(<AppShell><div>Workspace</div></AppShell>);

  await waitFor(() => expect(screen.getByText("API").closest("span")).toHaveAttribute("title", "API unavailable"));
  expect(screen.getByText("Runner").closest("span")).toHaveAttribute("title", "Runner unavailable");
});
