import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { RunResultTabs } from "@/components/runs/RunResultTabs";
import type { Run } from "@/lib/types";

const run: Run = { id: "run1", status: "NEEDS_ATTENTION", trigger_source: "MANUAL", attempt_count: 1, created_at: "2026-10-11T00:00:00Z", script_snapshot: "print('saved script')", visual_outcome: "NOT_REVIEWED", artifacts: [
  { id: "shot1", kind: "screenshot", media_type: "image/png", storage_path: "run1/screenshot.png" },
  { id: "vid1", kind: "video", media_type: "video/webm", storage_path: "run1/session.webm" },
] };

test("failed runs keep their script and inline image and video evidence available", () => {
  const { container } = render(<RunResultTabs run={run} runEvents={[]}/>);
  expect(screen.getByRole("tab", { name: "Steps & Logs" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Playwright Script" }));
  expect(screen.getByText(/saved script/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Screenshots" }));
  expect(screen.getByRole("img", { name: "screenshot.png" }).getAttribute("src")).toMatch(/\/api\/artifacts\/shot1$/);
  fireEvent.click(screen.getByRole("tab", { name: "Recording" }));
  expect(container.querySelector("video[controls]")).toHaveAttribute("src", "/api/artifacts/vid1");
  fireEvent.click(screen.getByRole("tab", { name: "Visual" }));
  expect(screen.getByText(/Not reviewed/i)).toBeInTheDocument();
});

test("empty media states do not leave broken previews", () => {
  render(<RunResultTabs run={{ ...run, artifacts: [] }} runEvents={[]}/>);
  fireEvent.click(screen.getByRole("tab", { name: "Screenshots" }));
  expect(screen.getByText(/No screenshots captured/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Recording" }));
  expect(screen.getByText(/No recording captured/i)).toBeInTheDocument();
});
