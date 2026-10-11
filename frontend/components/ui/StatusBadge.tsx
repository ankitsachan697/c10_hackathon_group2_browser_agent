import { CheckCircle2, CircleAlert, LoaderCircle } from "lucide-react";
import { activeExecutionStates } from "./ExecutionButton";

export function StatusBadge({ status }: { status: string }) {
  const tone = status.includes("PASS") ? "success" : status.includes("ATTENTION") || status.includes("FAIL") ? "danger" : "neutral";
  const active = activeExecutionStates.includes(status);
  const Icon = active ? LoaderCircle : tone === "success" ? CheckCircle2 : tone === "danger" ? CircleAlert : null;
  return <span className={`status status-${tone} ${active ? "status-active" : ""}`}>
    {Icon && <Icon aria-hidden="true" size={13} className={active ? "execution-spinner" : ""}/>} {status.replaceAll("_", " ")}
    {active && <span aria-hidden="true" className="execution-dot"/>}
  </span>;
}
