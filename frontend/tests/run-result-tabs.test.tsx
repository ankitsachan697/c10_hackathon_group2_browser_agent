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
  expect(screen.getAllByRole("tablist")).toHaveLength(1);
  expect(screen.queryByRole("tab", { name: "Steps & Logs" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("tab").map(tab => tab.textContent)).toEqual(["Step progression", "Live console", "Playwright Script", "Screenshots", "Recording", "Visual"]);
  fireEvent.click(screen.getByRole("tab", { name: "Playwright Script" }));
  expect(screen.getByText(/saved script/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Screenshots" }));
  expect(screen.getByRole("img", { name: "screenshot.png" }).getAttribute("src")).toMatch(/\/api\/artifacts\/shot1$/);
  fireEvent.click(screen.getByRole("tab", { name: "Recording" }));
  expect(container.querySelector("video[controls]")).toHaveAttribute("src", "/api/artifacts/vid1");
  fireEvent.click(screen.getByRole("tab", { name: "Visual" }));
  expect(screen.getByText(/Not reviewed/i)).toBeInTheDocument();
});

test("keyboard navigation moves from the live console to script in the same tab row", () => {
  render(<RunResultTabs run={run} runEvents={[]}/>);
  const consoleTab = screen.getByRole("tab", { name: "Live console" });
  fireEvent.click(consoleTab);
  fireEvent.keyDown(consoleTab, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Playwright Script" })).toHaveFocus();
  expect(screen.getByRole("tab", { name: "Playwright Script" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel")).toHaveTextContent("saved script");
});

test("empty media states do not leave broken previews", () => {
  render(<RunResultTabs run={{ ...run, artifacts: [] }} runEvents={[]}/>);
  fireEvent.click(screen.getByRole("tab", { name: "Screenshots" }));
  expect(screen.getByText(/No screenshots captured/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Recording" }));
  expect(screen.getByText(/No recording captured/i)).toBeInTheDocument();
});

test("expired recording retries a fresh capability and restores the playback position", () => {
  const { container } = render(<RunResultTabs run={run} runEvents={[]}/>);
  fireEvent.click(screen.getByRole("tab", { name: "Recording" }));
  const video = container.querySelector("video")!;
  video.currentTime = 7;
  fireEvent.error(video);
  expect(container.querySelector("video")).toHaveAttribute("src", "/api/artifacts/vid1?refresh=1");
  fireEvent.loadedMetadata(container.querySelector("video")!);
  expect(container.querySelector("video")!.currentTime).toBe(7);
  fireEvent.error(container.querySelector("video")!);
  fireEvent.error(container.querySelector("video")!);
  expect(screen.getByText(/Preview unavailable/)).toBeInTheDocument();
});
