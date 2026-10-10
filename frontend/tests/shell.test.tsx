import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { AppShell } from "@/components/shell/AppShell";

vi.mock("next/navigation", () => ({ usePathname: () => "/projects" }));

test("renders branded navigation and service health", () => {
  render(<AppShell><div>Workspace</div></AppShell>);
  expect(screen.getByAltText("Outskill")).toBeInTheDocument();
  expect(screen.getByRole("navigation")).toHaveTextContent("Overview");
  expect(screen.getByRole("navigation")).toHaveTextContent("Projects");
  expect(screen.getByText("Runner")).toBeInTheDocument();
  expect(screen.getByText("Workspace")).toBeInTheDocument();
});
