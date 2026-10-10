export function StatusBadge({ status }: { status: string }) {
  const tone = status.includes("PASS") ? "success" : status.includes("ATTENTION") || status.includes("FAIL") ? "danger" : "neutral";
  return <span className={`status status-${tone}`}>{status.replaceAll("_", " ")}</span>;
}
