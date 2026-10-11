"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ActionMenu } from "@/components/ui/ActionMenu";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

const activeStatuses = ["QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING"];
export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void api<Run[]>("/api/runs").then(value => { if (active) setRuns(value); }).catch(failure => { if (active) setError(failure.message); }).finally(() => { if (active) setReady(true); });
    return () => { active = false; };
  }, []);
  const remove = async () => {
    if (!deleting || busy) return;
    setBusy(true); setError("");
    try { await api(`/api/runs/${deleting.id}`, { method: "DELETE" }); setRuns(items => items.filter(item => item.id !== deleting.id)); setDeleting(null); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Run could not be deleted"); }
    finally { setBusy(false); }
  };
  return <div className="page"><div className="page-heading"><div><p className="eyebrow">Execution history</p><h1>Runs</h1><p>Open a run to inspect evidence or replay its saved script. Active runs cannot be deleted.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {!ready ? <div className="skeleton">Loading runs…</div> : runs.length === 0 ? <EmptyState title="No runs yet" detail="Run a saved journey to see its evidence here."/> : <DataTable headers={["Run", "Trigger", "Attempts", "Status", ""]}>{runs.map(run => <tr key={run.id}><td><Link href={`/runs/${run.id}`}>{run.id.slice(0, 12)}</Link></td><td>{run.trigger_source}</td><td>{run.attempt_count}</td><td><StatusBadge status={run.status}/></td><td><ActionMenu label={`Actions for ${run.id.slice(0, 12)}`}><button role="menuitem" disabled={activeStatuses.includes(run.status)} onClick={() => setDeleting(run)}><Trash2 size={14}/>Delete run</button></ActionMenu></td></tr>)}</DataTable>}
    <ConfirmDialog open={Boolean(deleting)} title="Delete this run?" confirmLabel={busy ? "Deleting…" : "Delete run"} onClose={() => { if (!busy) setDeleting(null); }} onConfirm={() => void remove()}>The run and its history will be removed. Evidence files move to recoverable trash; the journey and its locked baseline stay intact.</ConfirmDialog>
  </div>;
}
