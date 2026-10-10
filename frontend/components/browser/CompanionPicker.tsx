"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Device = { id: string; name: string; online: boolean };
type Capabilities = { location: "local" | "hosted" | "unavailable"; headed_supported: boolean; reason?: string | null };

export function CompanionPicker({ mode, onModeChange, companionId, onCompanionChange }: {
  mode: "headless" | "headed";
  onModeChange: (value: "headless" | "headed") => void;
  companionId: string;
  onCompanionChange: (value: string) => void;
}) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [state, available] = await Promise.all([
        api<Capabilities>("/api/companions/capabilities"), api<Device[]>("/api/companions"),
      ]);
      setCapabilities(state);
      setDevices(Array.isArray(available) ? available : []);
      setError("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Browser availability is unknown");
    }
  }, []);
  useEffect(() => { void Promise.resolve().then(refresh); }, [refresh]);

  const headedAvailable = capabilities?.headed_supported === true;
  const selectHeaded = () => {
    if (!headedAvailable) return;
    onModeChange("headed");
    if (capabilities?.location === "hosted") onCompanionChange(companionId || devices[0]?.id || "");
    else onCompanionChange("");
  };

  return <div className="browser-picker">
    <div className="browser-mode-options" role="radiogroup" aria-label="Browser mode">
      <label className={mode === "headless" ? "mode-card selected" : "mode-card"}><input type="radio" name="browser_mode" checked={mode === "headless"} onChange={() => { onModeChange("headless"); onCompanionChange(""); }}/><strong>Headless</strong><span>Run in the configured browser worker.</span></label>
      <label className={mode === "headed" ? "mode-card selected" : "mode-card"}><input type="radio" name="browser_mode" checked={mode === "headed"} disabled={!headedAvailable} onChange={selectHeaded}/><strong>Watch in browser</strong><span>{capabilities?.location === "hosted" ? "Approve the browser on your paired computer." : "Show Chromium at the browser worker."}</span></label>
    </div>
    {capabilities?.location === "hosted" && mode === "headed" && <label className="browser-device-label">Local browser<select aria-label="Local browser" value={companionId} onChange={event => onCompanionChange(event.target.value)}>{devices.map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></label>}
    {!headedAvailable && <p className="browser-picker-note">{error || capabilities?.reason || "Checking visible browser availability…"} <Link href="/settings">Browser setup</Link></p>}
    {capabilities?.location === "hosted" && mode === "headed" && <p className="browser-picker-note">The companion will ask you to approve this run before opening local Chromium.</p>}
    <button type="button" className="browser-refresh" onClick={() => void refresh()}>Refresh browser status</button>
  </div>;
}
