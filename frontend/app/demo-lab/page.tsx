"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, ExternalLink, FlaskConical, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

type Scenario = { id: string; target_path: string; locator_revision: 0 | 1; visual_variant: boolean; checkout_failure: boolean };
const objective = 'Sign in using the supplied credentials and validate "Logged In Successfully". Add one Studio Notebook to cart, open View cart, proceed to Checkout, fill Full name with "Demo Tester", Shipping email with "tester@example.test", Shipping address with "123 Example Street", then Place demo order. Assert the heading "Order confirmed" is visible. Capture screenshots at login, cart, and confirmation. Use exact accessible names for form labels and buttons, and a 5 second default action timeout.';

export default function DemoLabPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState("");
  const [origin, setOrigin] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    void Promise.resolve().then(() => setOrigin(window.location.origin));
    void api<Scenario[]>("/api/demo-lab/scenarios").then(values => { setScenarios(values); setSelected(values[0]?.id ?? ""); }).catch(failure => setError(failure.message)).finally(() => setLoading(false));
  }, []);
  const current = scenarios.find(item => item.id === selected);
  const target = current ? origin + current.target_path : "";
  const create = async () => {
    setBusy(true); setError(""); setNotice("");
    try { const value = await api<Scenario>("/api/demo-lab/scenarios", { method: "POST", body: "{}" }); setScenarios(items => [value, ...items]); setSelected(value.id); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Could not create scenario"); }
    finally { setBusy(false); }
  };
  const change = async (values: Partial<Scenario>) => {
    if (!current || busy) return;
    setBusy(true); setError(""); setNotice("");
    try { const value = await api<Scenario>(`/api/demo-lab/scenarios/${current.id}`, { method: "PATCH", body: JSON.stringify(values) }); setScenarios(items => items.map(item => item.id === value.id ? value : item)); setNotice("Target updated. Reload the shop or replay the saved journey to see the change."); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Could not update target"); }
    finally { setBusy(false); }
  };
  const copy = async (value: string) => {
    try { await navigator.clipboard.writeText(value); setNotice("Copied to clipboard."); }
    catch { setError("Clipboard unavailable. Select the text and copy it manually."); }
  };
  return <div className="page demo-lab">
    <div className="page-heading"><div><p className="eyebrow">Group2 · Hackathon playground</p><h1>Demo lab</h1><p>A real browser target for registration, login, cart, checkout, repair, and visual comparisons.</p></div><Button onClick={() => void create()} disabled={busy || loading} className="primary-link"><Plus size={15}/>New scenario</Button></div>
    {error && <p role="alert" className="form-error">{error}</p>}{notice && <p role="status" className="muted">{notice}</p>}
    <Card><div className="demo-heading"><FlaskConical size={20}/><div><h2>1. Prepare a clean target</h2><p className="muted">Each scenario has independent switches. Nothing is a real purchase; use synthetic data only.</p></div></div>
      {scenarios.length ? <div className="form-grid"><label>Demo scenario<select value={selected} onChange={event => setSelected(event.target.value)}>{scenarios.map(item => <option key={item.id} value={item.id}>Scenario {item.id.slice(0, 8)}</option>)}</select></label><label>Target URL<input readOnly value={target}/></label></div> : <p className="muted">Create a scenario to get your own deployable shop URL.</p>}
      {current && <div className="run-actions demo-links"><Button onClick={() => void copy(target)}><Copy size={14}/>Copy URL</Button><a className="button button-secondary" href={target} target="_blank" rel="noreferrer"><ExternalLink size={14}/>Open demo shop</a><Link className="button primary-link" href={`/journeys/new?${new URLSearchParams({ target_url: target, objective, name: "Demo shop checkout", username: "demo@example.test" })}`}>Create demo journey</Link></div>}
    </Card>
    <Card><h2>2. Verify and save a baseline</h2><p className="muted">Use n8n discovery for the first journey. Replay saved scripts for every subsequent run.</p><label className="objective-editor">Suggested objective<textarea readOnly rows={5} value={objective}/></label><div className="run-actions demo-links"><Button onClick={() => void copy(objective)}><Copy size={14}/>Copy objective</Button><span className="muted">Synthetic account: <code>demo@example.test</code> · Password: <code>DemoPass123!</code></span></div><p className="muted">For registration, click Register, supply a new synthetic email and a password of at least 8 characters, then sign in. Accounts reset when the page reloads.</p></Card>
    <Card><h2>3. Change the target, then replay</h2><div className="demo-switches">
      <label><input type="checkbox" checked={Boolean(current?.locator_revision)} disabled={!current || busy} onChange={event => void change({ locator_revision: event.target.checked ? 1 : 0 })}/><span><strong>Change checkout locator</strong><small>Checkout becomes Continue to shipping with a new ID. A stale saved locator should invoke repair once.</small></span></label>
      <label><input type="checkbox" checked={current?.visual_variant ?? false} disabled={!current || busy} onChange={event => void change({ visual_variant: event.target.checked })}/><span><strong>Apply visual redesign</strong><small>Change colors, borders, and spacing without changing the purchase flow. The locked baseline stays intact.</small></span></label>
      <label><input type="checkbox" checked={current?.checkout_failure ?? false} disabled={!current || busy} onChange={event => void change({ checkout_failure: event.target.checked })}/><span><strong>Reject checkout</strong><small>A genuine product failure. The confirmation assertion must fail and require attention—not be auto-healed.</small></span></label>
    </div><div className="run-actions demo-links"><Button disabled={!current || busy} onClick={() => void change({ locator_revision: 0, visual_variant: false, checkout_failure: false })}>Reset target</Button><Link href="/runs" className="button primary-link">Open runs and replay</Link></div></Card>
    <p className="muted">Local Docker automatically reaches loopback URLs through its host gateway. For remote use, open Studio at its deployed origin and create a fresh scenario there. Headed mode uses a paired local browser from Settings.</p>
  </div>;
}
