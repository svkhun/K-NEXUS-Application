# Savings update from k-flowsense-trustgraph

## Source and scope

Read the current source `src/app_v2.py`, `tests/test_savings_flow.py`, `frontend/react-app/src/components/MicroSweepVault.jsx`, `FlowSensePage.jsx`, README and commits `cd661879cddc1ad6163b4ce4d80616ee223c99d3` (opt-in savings / standard withdrawals) and `c484c16` (homepage render fix). The web app ports the financial behavior into its own session-protected API and existing mobile theme. Source illustrations with fixed THB 8,400 living costs / THB 5,000 buffer are not copied as live calculations.

## Current behavior

- Savings starts disabled, per visitor and persona. Turning it on or off changes preference only; no funds move automatically. Resetting a persona or applying a demo preset disables it again.
- The source capacity rule reserves `max(average daily spend, posted spend today, 0) × days until next payday`, all three profile bills, and `max(THB 500, profile emergency buffer)`. The payday is the next 28th using Bangkok dates, including month/year/leap-year boundaries.
- The web app retains its additional guard against the forecast minimum before payday. The final capacity is the smaller nonnegative amount from the source formula and existing forecast guard. Capacity details expose the extra reserve adjustment, so the UI explains differences from the simple formula.
- Each requested sweep must be positive, at most two decimals, no more than the freshly calculated capacity and at most THB 500. The default recommendation remains the original percentage-based micro amount, capped by the same guard. Repeated saves recalculate remaining headroom.
- Withdrawals require an explicit positive amount, no more than the savings balance, with at most two decimals. Selecting “ถอนทั้งหมด” fills the current balance before the user submits. Withdrawals remain available while saving is disabled. There is no special Undo or automatic all-balance fallback.
- The combined main/savings balance is conserved. Withdrawals do not count as daily spending. Preferences, events, balances and idempotency replies remain isolated to the visitor session. No dependency/model/dataset changes are required.

## API

| Route | Request / behavior |
| --- | --- |
| `GET /api/v2/flowsense/profile/{id}` | Adds `savings_enabled`, nested `savings_capacity`, persona withdrawal mode `STANDARD_WITHDRAWAL`; removes `undo_amount` and automatic-saving state |
| `GET /api/v2/flowsense/horizon-status/{id}` | Numeric `savings_capacity` retained; adds `max_sweep_amount` and `savings_estimate` breakdown |
| `POST /api/v2/flowsense/savings-preference` | `{account_id, enabled}`; no money movement |
| `POST /api/v2/flowsense/micro-sweep` | `{account_id, custom_sweep_amount?}`; enabled preference and current liquidity required |
| `POST /api/v2/flowsense/vault/withdraw` | `{account_id, amount}`; ordinary withdrawal independent of savings preference |
| `POST /api/v2/flowsense/recall` | Alias for the same explicit-amount withdrawal; old `mode` requests rejected |
| Former `/auto-saving`, `/auto-cycle` | Removed; return 404 |

All mutations use the existing signed HttpOnly session, exact-origin/CSRF protection, strict JSON schemas, body/rate limits, serialized session operations and idempotency middleware. Source legacy public-state/API fallback behavior was not imported.

## Verification

- 34 Python tests, including eight new savings formula/HTTP regressions, pass. They cover consent, a capacity below THB 500, repeated sweeps until zero capacity, insufficient liquidity, currency precision, explicit withdrawal validation, replay prevention, conservation, reset, session isolation, retired automation and calendar boundaries.
- Ten frontend logic tests and the production Vite build pass.
- Browser checks cover the savings screen at phone and desktop widths, consent without debit, saving THB 200.25, rejection of an input above THB 500, partial/full withdrawal while disabled, depleted savings, formula/scenario disclosure and mobile overflow.

The data, financial estimates and transactions remain synthetic demonstration behavior. Session state expires or resets on deployment/restart; no real account, guaranteed liquidity, scheduled savings or interest accrual is implied.
