import { Card } from "@/components/ui/Card";

export default function SettingsPage() {
  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Workspace configuration</p><h1>Settings</h1><p>Safe defaults are tracked in configuration; tokens stay in the backend runtime.</p></div></div>
    <div className="settings-grid">
      <Card><h2>Browser runner</h2><p>Headless runs use the isolated Playwright worker. A visible browser requires a configured local target or a paired companion; the create form reports availability.</p></Card>
      <Card><h2>Agent connections</h2><p>Discovery runs for a new journey. Saved-script runs skip it; eligible failures may call repair once. Visual review receives compact comparison metrics.</p></Card>
      <Card><h2>Daily regression</h2><p>Schedules use saved scripts and run headless at the selected local time and timezone. You can also start a saved journey on demand.</p></Card>
    </div>
    <Card><p className="eyebrow">Watch on your computer</p><h2>Pair a local browser</h2><p className="muted">An operator first sets a private companion admin token on the backend and enables hosted browser location. Generate a short-lived pair code through the protected API, then pair and start the companion on the computer where Chromium should appear.</p>
      <ol className="setup-steps"><li>Set <code>COMPANION_ADMIN_TOKEN</code>, <code>RUNNER_BROWSER_LOCATION=hosted</code>, and a reachable <code>RUNNER_RELAY_BASE_URL</code> on the backend.</li><li>As an operator, request <code>POST /api/companions/pair-codes</code> with the token in the <code>X-Companion-Admin-Token</code> header.</li><li>On your computer, run <code>python -m companion.browser_companion pair --server https://YOUR_BACKEND --code YOUR_CODE --device-name My-laptop</code>, then <code>python -m companion.browser_companion run --server https://YOUR_BACKEND</code>.</li><li>Select the online device in a new journey. The companion asks for approval before opening local Chromium.</li></ol>
      <p className="muted">No public Chrome debugging port is needed. Never paste the admin token or device credential into this page.</p>
    </Card>
  </div>;
}
