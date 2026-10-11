"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RotateCcw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RunTimeline } from "@/components/runs/RunTimeline";
import { RunEvidence } from "@/components/runs/RunEvidence";
import { RunScript } from "@/components/runs/RunScript";
import { RunRepair } from "@/components/runs/RunRepair";
import { RunActivity } from "@/components/runs/RunActivity";
import { RunVisual } from "@/components/runs/RunVisual";
import { RunMedia } from "@/components/runs/RunMedia";

const labels: Record<string, string> = {
  PASSED_AFTER_REPAIR: "Passed after repair", NEEDS_ATTENTION: "Needs attention", PASSED: "Passed", FAILED: "Failed",
};

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const [id, setId] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [tab, setTab] = useState("Evidence");
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { void Promise.resolve(params).then(value => setId(value.id)); }, [params]);
  useEffect(() => {
    if (!id) return;
    let active = true;
    void api<Run>(`/api/runs/${id}`).then(value => { if (active) setRun(value); }).catch(failure => { if (active) setError(failure instanceof Error ? failure.message : "Run unavailable"); });
    const timer = window.setInterval(() => {
      void api<Run>(`/api/runs/${id}`).then(value => { if (active) setRun(value); }).catch(() => undefined);
    }, 1800);
    return () => { active = false; window.clearInterval(timer); };
  }, [id]);
  if (!run) return <div className="skeleton">{error || "Loading run…"}</div>;
  const rerun = async (mode: "current" | "snapshot") => {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const next = await api<Run>(`/api/runs/${id}/rerun`, { method: "POST", body: JSON.stringify({ mode, background: true }) });
      router.push(`/runs/${next.id}`);
      setRun(next);
      setId(next.id);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not start rerun"); }
    finally { setBusy(false); }
  };
  const tabs = ["Evidence", "Screenshots", "Recording", "Script", "Repair", "Activity", "Visual"];
  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Run {run.id.slice(0, 12)}</p><h1>{labels[run.status] ?? run.status}</h1><StatusBadge status={run.status}/></div>
      <div className="run-actions"><Button disabled={busy || ["QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING"].includes(run.status)} aria-label="Run current script" onClick={() => void rerun("current")}><RotateCcw size={15}/>Run current script</Button><Button disabled={busy || ["QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING"].includes(run.status)} aria-label="Run this version" onClick={() => void rerun("snapshot")}>Run this version</Button><Button disabled={busy || ["QUEUED", "RUNNING", "DIAGNOSING", "REPAIRING", "RETRYING"].includes(run.status)} aria-label="Delete run" className="button-secondary" onClick={() => setConfirm(true)}><Trash2 size={15}/></Button></div>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="run-meta"><span>Saved script v{run.script_version ?? "—"}</span><span>Trigger: {run.trigger_source ?? "First run"}</span><span>Attempts: {run.attempt_count}</span>{run.visual_outcome && <span>Visual: {run.visual_outcome.replaceAll("_", " ")}</span>}</div>
    <RunTimeline run={run}/>
    <div className="tabs" role="tablist">{tabs.map(name => <button role="tab" aria-selected={tab === name} key={name} onClick={() => setTab(name)}>{name}</button>)}</div>
    {tab === "Evidence" && <RunEvidence artifacts={run.artifacts}/>}
    {tab === "Screenshots" && <RunMedia artifacts={run.artifacts ?? []} kind="screenshot"/>}
    {tab === "Recording" && <RunMedia artifacts={run.artifacts ?? []} kind="video"/>}
    {tab === "Script" && <RunScript original={run.script_snapshot ?? ""} healed={run.repair_patch}/>}
    {tab === "Repair" && <RunRepair original={run.script_snapshot ?? ""} healed={run.repair_patch} diagnosis={run.diagnosis_json}/>}
    {tab === "Activity" && <RunActivity runId={run.id}/>}
    {tab === "Visual" && <RunVisual run={run}/>}
    <ConfirmDialog open={confirm} title="Delete this run?" confirmLabel="Delete run" onClose={() => setConfirm(false)} onConfirm={async () => { try { await api(`/api/runs/${id}`, { method: "DELETE" }); setConfirm(false); router.push("/runs"); } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not delete run"); setConfirm(false); } }}>Evidence will move to recoverable trash. The saved journey and baseline are preserved.</ConfirmDialog>
  </div>;
}
