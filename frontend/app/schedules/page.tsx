"use client";

import { useEffect, useState } from "react";
import { Play, Plus, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Journey, Project, Schedule } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";

export default function SchedulesPage() {
  const [items, setItems] = useState<Schedule[]>([]);
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [ready, setReady] = useState(false);
  const [creating, setCreating] = useState(false);
  const [scopeType, setScopeType] = useState<"journey" | "project">("journey");
  const [scopeId, setScopeId] = useState("");
  const [localTime, setLocalTime] = useState("09:00");
  const [timezone, setTimezone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone);
  const toast = useToast();

  const load = () => Promise.all([
    api<Schedule[]>("/api/schedules"), api<Journey[]>("/api/journeys"), api<Project[]>("/api/projects"),
  ]).then(([scheduleValues, journeyValues, projectValues]) => {
    setItems(scheduleValues); setJourneys(journeyValues); setProjects(projectValues);
    setScopeId(current => current || journeyValues[0]?.id || projectValues[0]?.id || "");
  }).finally(() => setReady(true));

  useEffect(() => { void load(); }, []);

  const run = async (id: string) => { await api(`/api/schedules/${id}/run`, { method: "POST" }); toast("Scheduled scope started"); };
  const toggle = async (item: Schedule) => { const updated = await api<Schedule>(`/api/schedules/${item.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !item.enabled }) }); setItems(values => values.map(value => value.id === item.id ? updated : value)); };
  const remove = async (id: string) => { await api(`/api/schedules/${id}`, { method: "DELETE" }); setItems(values => values.filter(value => value.id !== id)); toast("Schedule deleted; run history retained"); };
  const create = async () => {
    const payload = { local_time: localTime, timezone, [scopeType === "journey" ? "journey_id" : "project_id"]: scopeId };
    const value = await api<Schedule>("/api/schedules", { method: "POST", body: JSON.stringify(payload) });
    setItems(values => [value, ...values]); setCreating(false); toast("Daily regression scheduled");
  };
  const scopes = scopeType === "journey" ? journeys : projects;

  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Daily regression</p><h1>Schedules</h1><p>Choose a local time and timezone; saved scripts run without regeneration.</p></div><Button onClick={() => setCreating(value => !value)}>{creating ? <X size={16}/> : <Plus size={16}/>} {creating ? "Close" : "New schedule"}</Button></div>
    {creating && <div className="card"><div className="form-grid"><label>Scope type<select value={scopeType} onChange={event => { const next = event.target.value as "journey"|"project"; setScopeType(next); setScopeId(next === "journey" ? journeys[0]?.id ?? "" : projects[0]?.id ?? ""); }}><option value="journey">Journey</option><option value="project">Project</option></select></label><label>Scope<select value={scopeId} onChange={event => setScopeId(event.target.value)}>{scopes.map(scope => <option key={scope.id} value={scope.id}>{scope.name}</option>)}</select></label><label>Daily time<input type="time" value={localTime} onChange={event => setLocalTime(event.target.value)}/></label><label>Timezone<input value={timezone} onChange={event => setTimezone(event.target.value)}/></label></div><div className="wizard-actions"><Button onClick={create} disabled={!scopeId || !localTime || !timezone}>Create schedule</Button></div></div>}
    {!ready ? <div className="skeleton">Loading schedules…</div> : items.length === 0 ? <EmptyState title="No schedules" detail="Add a daily schedule for a journey or project."/> : <DataTable headers={["Scope", "Time", "Timezone", "Enabled", "Next run", ""]}>{items.map(item => <tr key={item.id}><td>{item.journey_id ? journeys.find(value => value.id === item.journey_id)?.name ?? "Journey" : projects.find(value => value.id === item.project_id)?.name ?? "Project"}</td><td>{item.local_time}</td><td>{item.timezone}</td><td><input aria-label="Enabled" title={`Schedule ${item.id}`} type="checkbox" checked={Boolean(item.enabled)} onChange={() => toggle(item)}/></td><td>{item.next_run ? new Date(item.next_run).toLocaleString() : "—"}</td><td><div className="run-actions"><Button aria-label="Run now" onClick={() => run(item.id)}><Play size={15}/>Run now</Button><Button aria-label="Delete schedule" className="button-secondary" onClick={() => remove(item.id)}><Trash2 size={15}/></Button></div></td></tr>)}</DataTable>}
  </div>;
}
