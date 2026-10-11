import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ExecutionButton } from "@/components/ui/ExecutionButton";

test.each([
  ["STARTING", "Starting", true], ["QUEUED", "Queued", true],
  ["RUNNING", "Executing", true], ["DIAGNOSING", "Diagnosing", true],
  ["REPAIRING", "Repairing", true], ["RETRYING", "Retrying", true],
  ["PASSED", "Passed", false], ["PASSED_AFTER_REPAIR", "Passed after repair", false],
  ["FAILED", "Failed", false], ["NEEDS_ATTENTION", "Needs attention", false],
  ["START_FAILED", "Could not start", false],
])("%s has visible feedback and prevents duplicate execution only while active", (status, label, active) => {
  const clicked = vi.fn();
  render(<ExecutionButton label="Run current script" status={status} onClick={clicked}/>);
  const button = screen.getByRole("button", { name: "Run current script" });
  expect(button).toHaveAttribute("aria-busy", String(active));
  expect(button.querySelector("[data-execution-icon]")).not.toBeNull();
  expect(screen.getByText(new RegExp(label))).toBeInTheDocument();
  if (active) {
    expect(button).toBeDisabled();
    expect(button.querySelector(".execution-dot")).not.toBeNull();
  } else {
    expect(button).toBeEnabled();
  }
  fireEvent.click(button);
  expect(clicked).toHaveBeenCalledTimes(active ? 0 : 1);
});

test("idle remains a clearly labelled run action", () => {
  render(<ExecutionButton label="Run this version"/>);
  expect(screen.getByRole("button", { name: "Run this version" })).toBeEnabled();
  expect(screen.getByText("Run this version")).toBeInTheDocument();
});
