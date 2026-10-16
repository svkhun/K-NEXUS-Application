# Function review: k-flowsense-trustgraph → K web application

Reviewed the original `README.md`, `src/app_v2.py`, `frontend/js/app.js`, generated datasets, and the new application's UI/API on 2026-10-15; savings rechecked against source commits `cd66187` and `c484c16` on 2026-10-16.

## Functional coverage

| Original capability | Where to try it | Implementation and corrections |
| --- | --- | --- |
| Three behavioral personas | Profile picker on every page | Independent balances, savings preference, event history and pending transfers per visitor and persona |
| Status Horizon and safe spending | Home / Accounts | Upcoming actual calendar dates; reserve emergency buffer; daily limit can reach zero |
| Commitment warnings / normal-dip suppression | Accounts / FlowSense scenario buttons | Three funded presets; warnings depend on projected balance after upcoming debits; a normal dip does not raise an alert |
| 30-day forecast and past spending | Home / Accounts chart | **30 future days plus today and seven synthetic past days**; original UI/API included only 22 future days; ONNX projection incorporates payday, rent, debt and utilities |
| Forecast inspection | Chart range buttons and day slider | 7 / 14 / 30 days, accessible keyboard/touch slider, daily spending / fixed debit / salary details, expandable simulated history |
| Surplus-only Micro-Sweep | FlowSense | The backend uses the forecast's minimum balance before payday, obligations, emergency buffer and minimum main balance; recommendation and manual amount share the same guard |
| Optional savings | ออมเงิน → เปิดการแยกเงินออม | Disabled by default; explicit per-persona/session consent; no balance change on enabling; reserve living costs, all profile bills, minimum THB 500 buffer and forecast minimum; at most THB 500 per action |
| Standard savings withdrawal | ออมเงิน → ถอนเงินออม | Explicit positive amount or full balance selected before submission; works with savings disabled; no Undo or implicit all-balance withdrawal |
| Routine transfers with no added steps | Transfer / known recipient | Real ONNX evaluation; debit once; visible receipt and measured server inference latency |
| Critical anomaly / direct reasoning | Transfer / inspect recipient | Full Thai reasons, recipient age, velocity and KYC metadata; model signals are synthetic; no funds moved while waiting |
| Risk-only cooldown / Micro-Auth | Visible transfer settings and review popup | Optional 15-minute server-enforced pause, enabled by default, then five-second simulated verification and explicit proceed/cancel; signed clearance still binds source, target, amount, visitor and evaluation nonce, expires after 120 seconds and is single-use |
| High-value step-up | Transfer / “ลองรายการมูลค่าสูง ฿50,000” | Resets and funds that visitor's simulated account to 60,000 so the 50,000 demo gate can actually be tried |
| Confirmed blocked destination | Transfer / blocked preset | Stops before high-value or verification branches; no debit |
| Transaction slip | Successful transfer | Downloadable UTF-8 text receipt with DEMO identifier and explicit statement that it is not proof of real payment |
| Account reset | Header / Accounts / FlowSense | Restores initial balances and preference, clears pending clearance and old event history |
| SecOps graph / node inspector / fit controls | Accounts → expandable data lab | Bounded sample of 18 original synthetic transactions, node labels, metadata, connected amounts, zoom and accessible selection; original private-style SecOps routes remain absent |
| Stream filter / KPIs | Accounts → data lab | Actual event feed for this visitor and persona, filters and refresh; scoped counts from up to 50 retained events; original hardcoded detection rates and pretend Kafka feed are not presented as live evidence |
| CASA scenario calculator | Accounts → data lab | Original population × adoption × monthly savings × 12 formula, interactive sliders; explicitly excludes withdrawals and is a scenario, not actual deposit growth |
| Architecture overview | Data lab | Actual CPU ONNX path described; Kafka / Feast / Triton identified as original target architecture |
| Banking reference / mobile navigation | All screens | Dark green sidebar, light account cards, mint feature promotion, standalone K, sticky mobile header, search, bottom navigation, safe-area padding and larger controls |

## Public-demo boundaries

This is an independent prototype, not K PLUS, MAKE or a bank integration. All source datasets and account presets are synthetic. There is no real identity verification, background bank event ingestion, real deposit interest, production fraud-detection claim or money movement. The graph is a labeled sample, not a reconstruction of the full network. The latency shown is measured server inference time for the current evaluation, not an SLA or a full end-to-end benchmark.

Session state and the bounded event history remain in memory. They survive a page reload during the session but expire after one hour or restart/deploy. More than one worker/instance requires shared storage. Changing a preset deliberately resets that persona before applying its demonstration balances; all presets use the current Bangkok date. Resetting or changing a preset also disables savings.

## Verification

- 34 HTTP/model tests: budget/calendar rules, source savings formula, explicit opt-in, savings limits and repeated depletion, standard withdrawal validation/replay/conservation, session isolation and the original transfer/security boundaries. Ten frontend logic tests also pass.
- Production Vite build; no new runtime dependencies.
- Browser trials: explicit opt-in, savings, partial/full withdrawals with savings disabled, resolving a commitment warning, forecast day selection, graph node inspection, CASA slider, mobile search, risky transfer with simulated verification, confirmation and receipt download.
- Responsive checks at 320, 390, 768 and 1440 pixels; 320px body minimum-width overflow corrected.


## Risk-only cooldown update — 16 October 2026

See [the cooldown policy](transfer-cooldown.md). Default-on 15-minute review is restricted to risky transfers; ordinary payments remain immediate and the blocked destination remains blocked. Settings apply to new transactions; cancellation clears that transaction's timer. Review results use a modal. The current suite contains 44 backend and 13 frontend tests.
