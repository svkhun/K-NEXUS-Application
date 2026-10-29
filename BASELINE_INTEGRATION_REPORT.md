# FlowSense baseline integration — local demo

29 October 2026 · Asia/Bangkok. **Local baseline is active and verified. No production release.**

## Active policy and defaults

Policy `history28-min7-scenario-abstain.v1`; product adapter `live-intraday-next-day.v1`.
Local default `FLOWSENSE_BASELINE_MODE=BASELINE`; production default `OFF`.
This switch is separate from `models/serving.json: flowsense_enabled=false` and cannot enable ML.

| Persona | Account | Actual default method | Daily non-bill assumption | Seeded posted today |
|---|---|---|---:|---:|
| เมย์ | ACC_0100 | SCENARIO, N0/28 | ฿350 | ฿120 |
| นนท์ | ACC_0101 | SCENARIO, N0/28 | ฿600 | ฿200 |
| แพรว | ACC_0150 | SCENARIO, N0/28 | ฿300 | ฿90 |

All three use `config/baseline-personas.v1.json`, version
`synthetic-persona-assumptions.2026-10-29.1`. These are explicit engineering
assumptions, independent of the legacy CSV transaction mean. They are not measured
daily spending. Each session stores the config digest, value in satang/day, source,
version, known_at, and effective date range (session start through 2099-12-31).
The long end date is a declared demo assumption, not evidence about future behavior.

Seeded posted-today amounts are separately attributed as synthetic session opening
assumptions already included in the current balance. Confirmed non-bill transfers
increment posted-today spending; saving/withdrawal and bill-linked transfers do not.
No session transaction automatically certifies a complete calendar day.

The shared selector in `src/baseline_policy.py` applies:

1. **HISTORY_MEAN:** exactly the 28 closed Bangkok dates before current midnight;
   at least 7 complete known dates. Known zero counts in N; missing, partial,
   invalid or unavailable dates do not. Integer satang numerator; Decimal mean
   rounded `ROUND_HALF_UP`, fixed throughout the projection. Returns N/28,
   exclusions, account/origin, source/version/hash and selection ID.
2. **SCENARIO:** when history is insufficient and an explicit applicable versioned
   non-bill daily assumption exists. Its known_at cannot be in the future and its
   effective range must cover the live date plus 30 future days.
3. **ABSTAIN:** null amount and reason when neither is available, or baseline is OFF.
   No zero fallback or healthy/safe financial claim.

`attach_prepared_history` bridges independently validated sealed ingestion history,
preserving its exact account, origin and request hash. It imports no historical
opening balance or outstanding bills. Wrong-account history is rejected; stale
origin cannot become current history. There is no public history-write endpoint,
automatic dataset import, invented USER→ACC mapping, date shifting, research dataset
generation, or cluster retraining. Legacy `cf_user_id` metadata is not used for history.

## Consumer/source mapping

| Consumer | Calculation and shared identity |
|---|---|
| Forecast API / chart | `liquidity_forecast.forecast`; one selected integer daily burn, same source/version/selection ID on future points; copied bill state; salary separately declared |
| Profile API | Returns the selector result, baseline mode, input_as_of, and separate seeded posted-today provenance |
| Horizon / daily plan | Same selected burn and actual projected balances; deterministic balance/bills/buffer allowance is explicitly separate |
| Savings capacity / sweep guard | Same burn for D−1 future days before payday; outstanding bills + emergency buffer + minimum projected balance guard; recalculated on every request |
| Transfer review / impact | Same basis plus before/after projection snapshots; deterministic allocation remains usable independently of forecast |
| Transfer fingerprint / confirm | Binds date, current funds, posted spend, current and upcoming bills, profile/reserve, selector and full history/scenario inputs; changes require fresh review before a debit |
| Frontend simulator | Explicit user-set budget: remaining budget today plus future days and known bills. It is not the baseline forecast; null inputs/facts stop simulation |
| TrustGraph | Original model, embedding, features and thresholds preserved. `ratio_to_daily_avg` remains explicit demo telemetry, not a new measured baseline feature |

All backend financial consumers now reserve the same bills through the day before
next payday, including **next-month bills** after this month's payday. This fixes a
discovered mismatch where the chart included those obligations but plan/transfer
allocation reserved only the current month. Monthly IDs, paid amounts and the
existing opening assumption are retained; future materialization occurs on copies.
An explicitly confirmed early future bill can materialize that same instance and
record its payment. No projection settles a session bill.

## Origin, bills and money semantics

- API mode `LIVE_INTRADAY_BASELINE`: actual current session snapshot, full Bangkok
  input_as_of, current-date anchor plus 30 future points starting **tomorrow**.
- Current balance already contains posted debits. No second subtraction of today's
  spending, no additional assumed burn today, and no synthetic salary credit today.
  Future monthly salary is projected on day 28. This is a product assumption, not
  a midnight-issued forecast or a real salary posting.
- Manual budget simulation may include additional spending today, as explicitly
  chosen by the user. Deterministic allowance adds posted spend back only to define
  the whole-day allowance, then subtracts it once for remaining today.
- Bills use the existing session instance IDs and remaining amounts, including
  early/partial/full/overdue payments and month rollover. Projection pays unpaid
  due/overdue amounts once on the first future day or due date, even into deficit.
  Original session balances, paid mirrors and bill instances are not changed by reads.
- Historical settled references remain classification evidence only. The accepted
  proposed.4 source/receipt validation and sealed midnight `IssueRegistry` are
  unchanged. They are not populated with an intraday current balance. No new default
  midnight record is fabricated when an opening snapshot is unavailable.
- Old illustrative 7-day reconstructed balances are removed from the active chart.
  The response has 31 points, rather than the historical 38. Consumers release
  together under the versioned adapter. This is an intentional response migration.
- ABSTAIN propagates null through all future balances, expense totals and dependent
  minima/capacity. Savings returns unavailable/reason and rejects the sweep with 409.
  Known balance/bill/buffer budgets and explicit withdrawals still work independently.

## Verification evidence

Evidence directory: `artifacts/baseline-integration/`.

| Verification | Final actual result | Evidence |
|---|---|---|
| Backend, 12 separately bounded unittest files | **148 passed**, 0 failed, 0 skipped | `check-results.json`, `test_*.log` |
| New baseline acceptance | **11 passed**, included above | `test_baseline_integration.log` |
| Frontend Node checks | **26 passed**, 0 failed/skipped | `ui.log` |
| Production frontend build | **PASSED**, Vite output written locally | `build.log` |
| Real HTTP, default SCENARIO, all 3 personas | **PASSED** | `http-scenario.json` |
| Real HTTP, HISTORY_MEAN fixture, all 3 personas | **PASSED**, N7/28, ฿85.71/day | `http-history_mean.json` |
| Real HTTP, ABSTAIN fixture, all 3 personas | **PASSED**, null forecast/capacity, rejected sweep | `http-abstain.json` |
| Real HTTP lost-response retry | **PASSED**, same key, same receipt, one debit after 2 attempts | `retry-http.json` |
| Real HTTP baseline OFF rollback | **PASSED**, BASELINE_DISABLED, deterministic budget retained, only TrustGraph loaded | `rollback-http.json` |
| Package integrity | **13/13 hashes match**, manifest pin matches | `package-integrity.json` |
| Actual in-app browser | **PASSED for the explicit smoke scope below** | `browser-*.jpg`, `browser-*-dom.txt`, `browser-verification.json` |

Backend checks cover N6/N7/N28, zero/missing/partial, HALF_UP, invalid scenario,
account/origin mismatch, fixed-clock payday/leap/year/month rollover, early/partial/
full/overdue bills, next-month consumer agreement, read/input immutability, stale
assumption/history review rejection, actual API propagation, CSRF/origin/host/input
validation, token/session binding, cooldown/blocked/cancel policy, idempotency and
main+vault conservation. Existing 63 isolated contract tests passed, including
immutable issued records and historical references. A new bridge check uses the
unchanged proposed.4 source fixture: mean 27,752 satang, N28, historical settled
bills add no reserve; its 2025 origin is rejected for current history. No dates move.

Real default HTTP smoke uses new cookies per persona and exercises healthy preset,
opt-in, save/replay/withdraw, normal review/cancel, risky cooldown and blocked policy.
The separate lost-response probe executes a normal transfer and retries through
the same command journal used by the UI. These requests never reset a user session.

Browser smoke actually selected เมย์/นนท์/แพรว and read their SCENARIO/source/value
on the profile surface. It exercised the plan and current-date chart, verified
HISTORY_MEAN N7/28 with visible fixture provenance, selected an ABSTAIN future point
showing gaps/—, and verified unavailable savings with disabled save controls while
withdrawal remained available. The final simulator build was reopened with ABSTAIN;
the deterministic manual plan stayed separate from the unavailable spending outlook.
Console checks on scenario/history surfaces returned no warnings/errors. Browser
smoke is not a claim that every transfer/savings branch was clicked in a browser.

The HISTORY browser/server data are **hand-authored acceptance declarations**, with
one zero plus six ฿100 days, explicitly named
`HAND_AUTHORED_ACCEPTANCE_FIXTURE_NOT_LEDGER`. They are not actual persona history,
not the accepted research dataset, and not a new generated research dataset.

Timeout policy: backend child processes 90s/file, Node 60s, build 90s; real HTTP
requests 10s. Initial sandboxed Windows probes stalled before app execution in
`asyncio`'s socketpair initialization (one bounded HTTP probe timed out at 35s;
see `http-probe.log`). Local loopback execution outside that restriction resolved
it. Initial missing-jsonschema and old response assertions failed, then were
resolved and the complete final suite passed. Schema tests read existing
jsonschema 4.26.0 from the read-only Showcase environment with bytecode writes
disabled; no dependency install or Showcase write occurred. An initial exploratory
unbounded probe was stopped; retained verification uses explicit limits.

Some full-page screenshot requests failed in the browser capture API; normal
viewport capture and DOM snapshots succeeded. Screenshot files use JPEG extension
matching the returned bytes. Locator timeouts were resolved by observing the native
summary/selector state; they are not represented as application test passes.

**Not run this round:** production deployment/live-process verification, physical
iPad/device QA, complete browser end-to-end money-action matrix, the full historical
215-case CLI conformance rerun, Docker/CI/load, model training/tuning/export,
new accuracy evaluation, or field/user-outcome studies. No timeout/skip is counted
as a pass. Node tests do not substitute for browser evidence.

## Running local demo and rollback

Default demo: **http://127.0.0.1:8023/**. New isolated process/session; existing user
processes/sessions were not reset. Separate acceptance fixtures: port 8020 HISTORY,
port 8021 ABSTAIN. The preliminary port 8019 process was stopped after supersession.
The temporary rollback process on port 8022 was stopped after saving its evidence.

From this repository, build with `npm run build`, then run:

```powershell
$env:PUBLIC_ORIGIN='http://127.0.0.1:8023'
$env:FLOWSENSE_BASELINE_MODE='BASELINE'
.venv/Scripts/python.exe -m uvicorn src.app_v2:app --host 127.0.0.1 --port 8023
```

Reproduce bounded checks (with a local environment that permits Windows loopback):

```powershell
$env:BASELINE_SCHEMA_SITE_PACKAGES='D:\All Project\k-flowsense-trustgraph\.venv\Lib\site-packages'
.venv/Scripts/python.exe scripts/verify_baseline.py
.venv/Scripts/python.exe scripts/baseline_http_smoke.py --base http://127.0.0.1:8023 --method SCENARIO
```

Rollback by starting a **new** process with `FLOWSENSE_BASELINE_MODE=OFF` (or use a
separate port to preserve current in-memory sessions). Forecast-dependent output
then abstains. Keep the new bill/retry/security fixes, adapter/null-aware UI and
existing TrustGraph pair. Do not revert the whole working tree, activate legacy
FlowSense, or silently fall back to its ONNX/profile mean. In-memory demo sessions
are process-local; restarting a process loses its demo state, so drain/finish any
session before deliberately restarting it.

Limitations: all financial inputs remain synthetic; persona defaults have no
validated current history; assumptions about future spending/salary/bills are not
accuracy or safety guarantees. HISTORY support needs an explicit trusted ingestion
adapter and a current matching origin; the demo does not certify daily coverage or
connect to a bank. Local defaults are not evidence of deployed configuration.

FlowSense ML flag and startup guard remain in place. Runtime creates only the
TrustGraph session; disabled FlowSense artifact bytes may still be hash-checked
for package integrity. Existing artifact parity tests explicitly load models as
tests; that is distinct from Application runtime. No mock predictor is called by
the live baseline. TrustGraph ONNX SHA-256:
`e290222ed939caabf5455d4aac17e1a7f680c9d395ebabb99e057367c449efe3`;
embedding SHA-256:
`3a5f0f348ae3578c65bb1ef2ad661e32adb7e7907bb929fbd26d3101ac136ab0`.

Changes are uncommitted. Pre-existing uncommitted work was retained. No train,
tune, export, commit, push, deploy, real money movement, or Showcase edit occurred.
