"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, CalendarClock, CircleAlert, WandSparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

type Overview = { pass_rate: number | null; needs_attention: number; repaired_runs: number; total_runs: number; completed_runs: number; active_runs: number; projects: number; journeys: number; next_schedule: { next_run: string; timezone: string } | null };
export default function OverviewPage() {
  const [metrics, setMetrics] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const refresh = () => { void api<Overview>("/api/overview").then(value => { if (active) { setMetrics(value); setError(""); } }).catch(failure => { if (active) setError(failure.message); }); };
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Group2 · Workspace overview</p><h1>Automation at a glance</h1><p>Live counts from saved runs, including verified repairs.</p></div><Link className="button button-secondary" href="/demo-lab">Open demo lab</Link></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="metric-grid">
      <Card><Activity/><span>Pass rate</span><strong>{metrics?.pass_rate != null ? `${metrics.pass_rate}%` : "—"}</strong><small>{metrics ? `${metrics.completed_runs} completed runs` : "Loading saved runs…"}</small></Card>
      <Card><CircleAlert/><span>Needs attention</span><strong>{metrics?.needs_attention ?? "—"}</strong><small>Failed and unresolved runs</small></Card>
      <Card><WandSparkles/><span>Repaired runs</span><strong>{metrics?.repaired_runs ?? "—"}</strong><small>Passed after one verified retry</small></Card>
      <Card><CalendarClock/><span>Next schedule</span><strong className="schedule-metric">{metrics?.next_schedule ? new Date(metrics.next_schedule.next_run).toLocaleString() : "—"}</strong><small><Link href="/schedules">{metrics?.next_schedule?.timezone ?? "Set a daily run"}</Link></small></Card>
    </section>
    {metrics && <p className="muted">{metrics.projects} projects · {metrics.journeys} saved journeys · {metrics.total_runs} runs · {metrics.active_runs} active. Active runs are excluded from the pass rate.</p>}
    <Card className="hero-card"><div><p className="eyebrow">Get started</p><h2>Build a reusable browser journey</h2><p>Generate once, verify in a real browser, then replay the saved script on demand or on schedule.</p></div><Link className="button primary-link" href="/journeys/new">Create journey</Link></Card>
  </div>;
}
