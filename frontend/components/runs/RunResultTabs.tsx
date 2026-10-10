"use client";

import { useState } from "react";
import type { ActivityEvent, Run } from "@/lib/types";
import { RunActivity } from "@/components/runs/RunActivity";
import { RunMedia } from "@/components/runs/RunMedia";
import { RunScript } from "@/components/runs/RunScript";
import { RunTimeline } from "@/components/runs/RunTimeline";
import { RunVisual } from "@/components/runs/RunVisual";

const tabs = ["Steps & Logs", "Playwright Script", "Screenshots", "Recording", "Visual"] as const;
type Tab = typeof tabs[number];

export function RunResultTabs({ run, runEvents }: { run: Run; runEvents: ActivityEvent[] }) {
  const [tab, setTab] = useState<Tab>("Steps & Logs");
  return <section className="run-result-tabs" aria-label="Run results">
    <div className="tabs" role="tablist" aria-label="Run evidence">{tabs.map(name => <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>{name}</button>)}</div>
    <div role="tabpanel" className="result-tab-panel">
      {tab === "Steps & Logs" && <><RunTimeline run={run}/><RunActivity runId={run.id} suppliedEvents={runEvents}/></>}
      {tab === "Playwright Script" && (run.script_snapshot ? <RunScript original={run.script_snapshot} healed={run.repair_patch}/> : <p className="evidence-empty">Script is not available yet.</p>)}
      {tab === "Screenshots" && <RunMedia artifacts={run.artifacts ?? []} kind="screenshot"/>}
      {tab === "Recording" && <RunMedia artifacts={run.artifacts ?? []} kind="video"/>}
      {tab === "Visual" && <RunVisual run={run}/>}
    </div>
  </section>;
}
