# Scenario UX/state fix — 30 October 2026 (Asia/Bangkok)

Status: implementation and local verification complete; commit, CI, deploy and public QA pending below. All money is synthetic.

## Confirmed root cause and release target

Render connector, canonical remote ref and public /release.json independently confirmed Application service `srv-dba8c061egvs739onubg` in `My Workspace` / `tea-dak0nuuq1p3s739rgbj0`, repository `svkhun/K-NEXUS-Application`, branch `codex/application-baseline-release-20261030`, autoDeploy `checksPass`, free Singapore Docker service, one instance, health `/api/v2/health`. Starting live commit `e5586c9286888a008fa0b1d6fca6d7e12d03b096`, deploy `dep-dbhojg7b9u1s73a7go00` was terminal live. No service configuration change is required.

The server stores per-visitor accounts, balances, bills, scenario, preferences, events and pending transfer reviews in a one-hour in-process session, selected by HttpOnly cookie. GET/navigation/refresh does not reset these. Scenario selection resets the selected account, preserves its reserve preference, then applies a preset. Explicit reset restores that persona's opening data, including default reserve preference. The browser formerly hid active context in a collapsed drawer, had no return-session explanation, and displayed null recommended savings as a pause. Fresh default main balances were 65% of salary; on 30 October May had main balance THB15,600 but zero daily allowance because bills plus buffer exceeded it by THB700. Public pre-change browser confirmed this distinction.

Main balance and vault are separate money amounts. Daily allowance is a deterministic allocation after bills and buffer, not main balance. Savings capacity is the surplus after projected living costs, bills, buffer and minimum projected liquidity. Chart zero ticks are coordinates, not account balances. SCENARIO spending method is a daily non-bill engineering assumption, distinct from the selectable demo situation. Loading/error/missing data are not money values.

localStorage stores only tutorial completion. sessionStorage stores the exact unresolved command journal (intent/body/key/session binding), and now a persona selection plus a session-visit marker; no browser balance/scenario label is treated as server truth. React keeps current page/review display; server restores pending review on page load. Refresh now also retains the selected persona.

## Resulting behavior and reset semantics

- Visible server-sourced active situation, change selector and default action on home, financial, account, savings, transactions, transfer and profile pages; server situation also appears inside review before transfer.
- A resumed server session offers ทดลองต่อ / เริ่มใหม่ once per selected persona per document visit; normal API refresh and navigation do not repeat it. Continue has no mutation. Expired/restarted sessions are described as new sessions, including when the browser still has an invalid old cookie.
- Scenario/default/high-value entry points show a native modal explaining exactly which persona's balances, vault, bills, preferences, events and review permissions restart. Cancel leaves data untouched. Scenario preserves chosen reserve; default restores configured persona reserve. Other personas and visitors are untouched.
- `config/demo-initialization.v1.json`, version `demo-opening.2026-10-30.1`, reuses existing healthy preset arithmetic only at new-account initialization or explicit reset with BASELINE enabled. All budget/capacity outputs use the existing engine. Default stays a distinct server `default` situation; choosing healthy remains an explicit separate action. OFF keeps prior profile opening and unavailable forecast/capacity. No mount scenario POST or forced positive output.
- Actual zero daily allowance explains bills/reserve, exhausted daily allocation or sub-satang rounding according to known inputs and shows real main/vault separately. Null capacity is unavailable with API reason. Loading renders a spinner; failed reload clears stale financial data and offers retry. Assumption method/source/version remain unchanged in a disclosure.
- Unknown browser commands retain their journal and block new commands/reset. Existing ambiguous server tombstones (no result or 5xx) also block destructive commands before mutation. Replay lookup still runs first. Reset never clears session idempotency tombstones/reply cache. Old review/nonces/clearance are invalidated for the selected persona, retaining original cooldown, blocked-recipient, CSRF, origin, cookie and session-token rules.
- Account activity is reset as disclosed; command receipts/replay data remain session-level. Pending review must be managed via return-to-review before UI reset. Unresolved command reconciliation has a separate receive-original-result action.

## Files and verification

Backend: `src/app_v2.py` (reuse preset helper, versioned opening), `src/demo_security.py` (lifecycle + ambiguous-reset guard). Frontend: `App.jsx`, `ScenarioPicker.jsx`, `SpendingBasis.jsx`, `DailyPlan.jsx`, `Dashboard.jsx`, `api.js`, `scenarios.css`, new `DemoResetDialog.jsx`, `DemoMoneyContext.jsx`, `demoContext.mjs`. Release identity in `scripts/build_release.mjs`; dedicated regression/public scripts and tests are included.

Local final backend: 154 PASS, zero failures/errors/skips/timeouts, bounded per file. Includes all three fresh personas, fixed Bangkok clock before/on payday, October/November rollover and leap day, resume/GET preservation, persona/visitor reset isolation, reserve semantics, ambiguous command guard, retry after reset one debit, stale review and clearance rejection, bill/partial bill/vault conservation, CSRF/cooldown/blocked policy. Three pre-existing full research-package/legacy parity checks remain NOT_RUN in the unchanged release runner; deployed runtime integrity checks pass. No ML training, tuning, evaluation or export was performed.

Frontend final: 34 PASS, zero failures/skips; actual component render checks cover zero vs null, real balances, assumption provenance, pending reset controls and actual App loading output. Production build PASS. Tests assert behavior; existing assertions/security policies were not weakened. Sandbox-only first attempt had loopback initialization TIMEOUT and temporary-directory permission errors; rerunning the same checks outside that restriction passed. Initial new test fixtures incorrectly sent extra confirm fields and compared volatile API timestamps; corrected to the existing command schema and complete server account state; failures are not counted as passes.

Local browser confirmed native confirmation, real risk main balance THB5,085 vs daily THB0, meaningful bill/reserve explanation, refresh/continue preservation and no captured console warning/error. An initial QA port outside the configured local origin was correctly rejected by security; QA moved to the allowed origin without changing policy. Local results do not establish public browser PASS.

## Preservation and rollback

Reused isolated release checkout at `artifacts/application-release-20261030/checkout`; original main checkout, HEAD, index and 1,626 inventoried source/untracked files are preserved and checked by SHA-256. Existing unrelated report edits and acceptance scratch files in the release checkout are excluded from this commit. Only explicit file paths are staged. No main push/merge, stash/reset/clean/force push. Approved model/config/data/contract files and TrustGraph embeddings/thresholds are unchanged; FlowSense ML remains disabled. Showcase is read-only and was not edited or deployed. No paid resources or configuration changes.

To roll back this UX release, revert only its reviewed source changes on the same release branch and let CI/Auto-Deploy run, preserving previous financial/security/approved-model baseline. Do not revert to the older main service build. Prefer retaining the new ambiguous-command guard. An authorized deployment/restart ends in-process synthetic sessions; never claim it restores old state. Browser journals with unresolved old-session commands remain available and cannot replay against new sessions.

## Publication evidence

Pending: final commit/source hash, CI URL/conclusion, Render deploy terminal status, identity/assets and fresh independent-cookie public HTTP matrix, public desktop/narrow browser flow, preservation check. Evidence will be appended after observed completion.
