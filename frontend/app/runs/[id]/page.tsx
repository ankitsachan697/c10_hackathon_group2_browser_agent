"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ExecutionButton, activeExecutionStates } from "@/components/ui/ExecutionButton";
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
  const [selectedAction, setSelectedAction] = useState<"current" | "snapshot" | null>(null);
  const [startFailed, setStartFailed] = useState(false);
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
    setBusy(true); setError(""); setSelectedAction(mode); setStartFailed(false);
    try {
      const next = await api<Run>(`/api/runs/${id}/rerun`, { method: "POST", body: JSON.stringify({ mode, background: true }) });
      router.push(`/runs/${next.id}`);
      setRun(next);
      setId(next.id);
    } catch (failure) { setStartFailed(true); setError(failure instanceof Error ? failure.message : "Could not start rerun"); }
    finally { setBusy(false); }
  };
  const tabs = ["Evidence", "Screenshots", "Recording", "Script", "Repair", "Activity", "Visual"];
  const runActive = activeExecutionStates.includes(run.status);
  const actionStatus = busy ? "STARTING" : startFailed ? "START_FAILED" : run.status;
  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Run {run.id.slice(0, 12)}</p><h1>{labels[run.status] ?? run.status}</h1><StatusBadge status={run.status}/></div>
      <div className="run-actions"><ExecutionButton label="Run current script" status={selectedAction === "current" || (!selectedAction && runActive) ? actionStatus : ""} disabled={busy || runActive} onClick={() => void rerun("current")}/><ExecutionButton label="Run this version" status={selectedAction === "snapshot" ? actionStatus : ""} disabled={busy || runActive} onClick={() => void rerun("snapshot")}/><Button disabled={busy || runActive} aria-label="Delete run" className="button-secondary" onClick={() => setConfirm(true)}><Trash2 size={15}/></Button></div>
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
