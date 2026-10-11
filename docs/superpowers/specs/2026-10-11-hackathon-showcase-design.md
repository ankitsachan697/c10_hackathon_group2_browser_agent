# Group2 showcase

Approved scope: build and verify a synthetic shop and showcase existing real agents. Keep native inline execution and current Outskill styling. No Kane CLI or real payments. Implementation remains in the current checkout on a feature branch for eventual merge into demo_master.

## Demo lab

Serve a standalone HTML/CSS/JavaScript shop from FastAPI under `/api/demo-shop/{id}`; Next's existing same-origin proxy makes this available at the deployed Studio origin. Persist isolated scenario switches in SQLite. Provide a Studio Demo lab page to create scenarios, copy objectives/URLs, and change three independent switches: stale checkout locator, visual redesign, rejected checkout. The target accepts only synthetic accounts and synthetic shipping details, supports registration, login, product/cart/checkout, and displays deterministic confirmation. No purchases or third-party requests.

Headless Docker workers must reach local targets: map loopback navigation to Docker host gateway only inside the isolated worker. Native discovery uses the original local URL. Remote deployment uses its actual public origin; Linux backend serving the demo must bind an interface reachable from its worker. Paired local Chromium is the existing headed execution option, not an exposed unauthenticated CDP port.

## Execution and evidence

Create scripts through real n8n discovery. Replay stored scripts on demand; induce a genuine stale-locator failure by changing the target, not the script. Invoke real repair once, retry once, retain both attempts and root cause. Assertions/business failures remain needs-attention, not rewritten into passes. Preserve baseline screenshot; show baseline/current/diff together and keep functional and visual verdicts separate. Record synthetic registration and wrong-credential/checkout error coverage as well as the repair path.

## Studio hygiene

Group2 badge next to Outskill. Dashboard aggregates persisted runs, excludes active/skipped runs from pass-rate denominator, counts repaired successes and unresolved outcomes, next enabled schedule. Add run deletion in history with explicit confirmation and block active run deletion; clear dependent history and agent audit references while moving artifacts into existing recoverable trash. Detail deletion returns to history.

## Deliverables

Real browser end-to-end evidence with agent IDs and run IDs; reproducible runbook; time-compressed video under 120 seconds with an explicit caption if waiting is shortened. Detailed explorable architecture HTML grounded in source, with automated and perceptual validation. Never claim a remote deployment or agent execution that was not actually tested. No credential values or private environment files in git or final deliverables.
