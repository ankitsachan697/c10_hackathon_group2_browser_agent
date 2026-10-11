import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { LiveRunProgress } from "@/components/runs/LiveRunProgress";
import type { ActivityEvent } from "@/lib/types";

const event = (seq: number, kind: string, payload: Record<string, unknown>, source = "playwright", scope_type: "run" | "operation" = "run"): ActivityEvent => ({ seq, kind, payload, source, scope_type, created_at: "2026-10-11T00:00:00Z" });

test("keeps planned discovery separate from confirmed actions across attempts", () => {
  render(<LiveRunProgress
    operationEvents={[event(1, "generation.completed", { discovered_steps: ["Log in", "Verify success message"] }, "agent", "operation")]}
    runEvents={[
      event(2, "action.started", { action: "fill", attempt: 1 }),
      event(3, "action.failed", { action: "fill", attempt: 1 }),
      event(4, "run.retry_started", { attempt: 2 }, "system"),
      event(5, "action.started", { action: "fill", attempt: 2 }),
      event(6, "action.finished", { action: "fill", attempt: 2 }),
      event(7, "run.attempt_finished", { attempt: 2, passed: false }, "system"),
      event(8, "log", { message: "password=[REDACTED]" }),
    ]}
    runStatus="NEEDS_ATTENTION"
  />);
  expect(screen.getByText("Log in")).toBeInTheDocument();
  expect(screen.getByText("Verify success message")).toBeInTheDocument();
  expect(screen.getByText(/Attempt 1.*fill.*failed/i)).toBeInTheDocument();
  expect(screen.getByText(/Attempt 2.*fill.*finished/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Needs attention" })).toBeInTheDocument();
  expect(screen.queryByText(/First run passed/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Live console" }));
  expect(screen.getByText(/password=\[REDACTED\]/)).toBeInTheDocument();
});
