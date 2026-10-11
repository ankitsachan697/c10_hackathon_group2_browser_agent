"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

type Health = { status: string; cloud_mode?: boolean; runner_ready?: boolean; n8n_connected?: boolean };
type Capability = { headed_supported: boolean; reason?: string; location?: string };

async function loadReadiness() {
  const [response, capability] = await Promise.all([fetch("/api/health", { cache: "no-store" }), api<Capability>("/api/companions/capabilities")]);
  if (!response.ok) throw new Error("Studio API is unavailable. Retry after the cloud session starts.");
  return { health: await response.json() as Health, browser: capability };
}

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [browser, setBrowser] = useState<Capability | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("headless");
  const refresh = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const value = await loadReadiness();
      setHealth(value.health); setBrowser(value.browser);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Readiness check failed"); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => {
    let active = true;
    void loadReadiness().then(value => {
      if (active) { setHealth(value.health); setBrowser(value.browser); }
    }).catch(failure => {
      if (active) setError(failure instanceof Error ? failure.message : "Readiness check failed");
    }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, []);
  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Workspace configuration</p><h1>Settings</h1><p>Check readiness, choose a browser, and follow the setup steps.</p></div><button className="button button-secondary" onClick={() => void refresh()} disabled={busy}><RefreshCw size={16} className={busy ? "execution-spinner" : ""}/>Refresh readiness</button></div>
    {error && <p className="error-banner" role="alert">{error}</p>}
    <div className="settings-grid" aria-live="polite">
      <Card><p className="eyebrow">Studio API</p><h2>{health ? "API ready" : "Checking API…"}</h2><p>Stores projects, saved scripts, run history, and evidence.</p></Card>
      <Card><p className="eyebrow">Headless execution</p><h2>{health?.runner_ready ? "Browser worker ready" : health?.cloud_mode ? "Cloud worker pending" : "Checking browser worker…"}</h2><p>A separate Chromium worker runs each script. New workers may take a minute to prepare.</p></Card>
      <Card><p className="eyebrow">n8n agents</p><h2>{health?.n8n_connected ? "Agent credentials configured" : "Agent setup required"}</h2><p>Discovery for new journeys; one eligible repair retry; visual analysis after screenshot comparison. Configuration is not proof of an agent invocation.</p></Card>
    </div>
    <div className="run-tab-bar" role="tablist" aria-label="Browser setup"><button role="tab" aria-selected={tab === "headless"} className={tab === "headless" ? "active" : ""} onClick={() => setTab("headless")}>Run remotely headless</button><button role="tab" aria-selected={tab === "headed"} className={tab === "headed" ? "active" : ""} onClick={() => setTab("headed")}>Watch local Chromium</button></div>
    {tab === "headless" ? <Card><p className="eyebrow">No local browser setup needed</p><h2>Run and inspect the captured evidence</h2><ol className="setup-steps"><li>Create or select a project, describe the objective, and enter its public HTTPS starting URL.</li><li>If login is required, use the separate username and password fields. Credentials are passed to the worker, not to discovery.</li><li>Select Headless, then Verify &amp; record live. Follow the active state and live browser actions.</li><li>Inspect the Playwright script, screenshots, recording, and visual comparison tabs. Rerun uses the saved script without another discovery call.</li></ol><p className="muted">The free cloud setup admits one job at a time with a ten-minute total budget. If the session is ending or the free quota is exhausted, the job is rejected before browser actions begin.</p><p className="muted">Daily cloud scheduling is not enabled yet. Saved scripts can be run on demand.</p></Card> : <Card><p className="eyebrow">Visible browser on your computer</p><h2>Install Chromium on your computer</h2><p>{browser?.headed_supported ? "An approved browser target is available." : browser?.reason || "Pairing is required before a visible browser can be selected."}</p><ol className="setup-steps"><li>From the repository, create a Python environment and install <code>backend/requirements.txt</code>, then run <code>python -m playwright install chromium</code>.</li><li>An operator configures a private companion admin token and a reachable WebSocket relay on the backend. Request a short-lived pairing code through <code>POST /api/companions/pair-codes</code>.</li><li>Run <code>python -m companion.browser_companion pair --server https://YOUR_BACKEND --code YOUR_CODE --device-name My-laptop</code>.</li><li>Start <code>python -m companion.browser_companion run --server https://YOUR_BACKEND</code>. Keep that terminal open, select the online device, and approve the run locally.</li></ol><p className="muted">No public debugging port is needed. Never paste an admin token into a journey. Remote headed execution remains unavailable until its paired-worker transport is verified; use remote Headless for now.</p></Card>}
  </div>;
}
