import { CheckCircle2, CircleAlert, LoaderCircle, Play, WandSparkles } from "lucide-react";
import { useId, type ButtonHTMLAttributes } from "react";
import { Button } from "./Button";

export const activeExecutionStates = ["STARTING", "QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING"];
const labels: Record<string, string> = {
  STARTING: "Starting…", QUEUED: "Queued…", RUNNING: "Executing…", DIAGNOSING: "Diagnosing…",
  REPAIRING: "Repairing…", RETRYING: "Retrying…", PASSED: "Passed", PASSED_AFTER_REPAIR: "Passed after repair",
  FAILED: "Failed", NEEDS_ATTENTION: "Needs attention", START_FAILED: "Could not start",
};

/** Feedback comes from persisted execution state, never a cosmetic timer. */
export function ExecutionButton({ label, status = "", disabled, className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string; status?: string }) {
  const stateId = useId();
  const active = activeExecutionStates.includes(status);
  const passed = status === "PASSED" || status === "PASSED_AFTER_REPAIR";
  const failed = ["FAILED", "NEEDS_ATTENTION", "START_FAILED"].includes(status);
  const Icon = active ? LoaderCircle : status === "PASSED_AFTER_REPAIR" ? WandSparkles : passed ? CheckCircle2 : failed ? CircleAlert : Play;
  return <Button {...props} aria-label={label} aria-describedby={stateId} aria-busy={active}
    disabled={disabled || active} data-execution-state={status || "IDLE"}
    className={`execution-button ${active ? "execution-active" : passed ? "execution-passed" : failed ? "execution-failed" : ""} ${className}`}>
    <Icon aria-hidden="true" data-execution-icon size={16} className={active ? "execution-spinner" : ""}/>
    <span id={stateId} aria-live="polite" aria-atomic="true">{labels[status] ? <>{labels[status]}{!active && <small>{label}</small>}</> : label}</span>
    {active && <span aria-hidden="true" className="execution-dot"/>}
  </Button>;
}
