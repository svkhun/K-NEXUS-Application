# ก่อนโอน เห็นผลต่อแผนเงิน — 17 October 2026

## Implemented behavior

`evaluate-transfer` is now preview-only for every risk tier. Routine transactions return `TRANSFER_REVIEW` with a signed `review_token`; they need explicit final confirmation but no artificial delay or simulated authentication. Risky and large-value transactions retain their existing simulated-auth paths. Blocked demo destinations cannot be authorized by bill selection, purpose selection, timers or tokens.

Every non-blocked review connects the existing capabilities: TrustGraph explains recipient signals; FlowSense displays the impact on remaining money. These dimensions are independent. A reserve shortfall never increases the fraud score; ample funds never lower it.

The calculation is an allocation rule, not model inference:

```
available = current balance - outstanding bills before payday - emergency reserve
average remaining daily allocation = floor_to_cents(max(0, available) / days until payday)
reserve shortfall = max(0, -available)
```

The signed available amount remains in the API even when negative. The UI shows zero allocation and the shortfall. The rule excludes savings not yet withdrawn and assumes the existing payday on the 28th. It differs from the home screen's remaining today, which accounts for posted discretionary spending. It is not a probability of financial safety.

## Explicit bill allocation

Bills have IDs scoped to their due date (`rent:2026-10-26`, for example). The user can allocate a full or partial payment to an unpaid bill before payday, including a bill due today, up to its remaining amount. This selection is not evidence of the recipient's identity.

Preview/cancellation never settle bills. Successful confirmation atomically debits the balance and records the bill payment without also counting it as discretionary daily spending. The remaining bill amount feeds the daily plan, savings reserve and forecast. Future cycles retain their full amount. An unpaid bill due today is conservatively included in the next forecast day. The existing calendar model assumes past scheduled obligations have occurred; it is not an arrears ledger or background payment scheduler.

Synthetic test example: balance 15,000; bills 7,160; reserve 1,000; 18 days to payday. A new 4,000 expense changes the average from 380 to 157.77/day. Paying reserved rent of 5,500 changes balance to 9,500 and bills to 1,660, preserving 380/day. These are arithmetic checks, not customer-impact evidence.

## Guidance and repeated payments

Optional context selects guidance for job/task payments, extra payments to withdraw funds, changed recipient accounts or general transfers. Context does not alter model features, scores or enforcement. Contacting a bank or finishing a timer does not certify safety. The app never contacts anyone on the user's behalf.

Reviews show successful transfer count/total to the same recipient today and the total if the request succeeds. Counters are independent of the 50-event feed. Preview/cancellation never count as successful transfers or erase past successes. Totals are visitor/persona/Thai-day scoped. They do not connect different recipients, classify scam sequences or represent all banking activity.

## Confirmation safety

Review and simulated-auth tokens have distinct purposes, binding session, source, recipient, amount and pending nonce. Confirmation uses the stored bill selection/context; the client cannot replace them. Re-evaluation rotates the nonce. Risky authentication and confirmation retain the server deadline.

Before debiting, confirmation compares balance, spending, paid bills, profile assumptions and Thai date to the reviewed snapshot. A mismatch returns HTTP 409 `PLAN_CHANGED` without moving money. Review again before confirming; an existing risky transaction retains its applicable cooldown. Debit, bill settlement and cumulative totals use the existing account/session serialization. Idempotency and nonce consumption prevent duplicate debits.

State expires after one hour or server restart. No real banking, biometric verification, external recipient verification or guaranteed liquidity was added.

## Validation and next research

New HTTP regressions cover preview without debit; the numeric example; full/partial bills; concurrent confirmation; overpayment; stale balance/date; token purpose/session binding; unchanged fraud policy; blocked recipients; cumulative totals; restore/cancel; invalid bills; and due-day forecasting. Existing security, savings, forecast and cooldown tests remain.

Verified: 56 Python tests (including 12 new planning tests), 13 frontend logic tests, and the production build pass. Browser checks cover bill payment, new spending impact, cumulative totals, cancellation, normal-review restoration, risk-only waiting, no horizontal overflow at 320/390 px, and no captured console warnings/errors.

Before claiming effectiveness, compare the existing warning to impact-plus-guidance using balanced legitimate/scam scenarios. Measure comprehension, verification actions, scam-scenario completion, legitimate-payment completion, time and frustration. Small exploratory usability samples find design problems but do not establish population-level fraud reduction.

Uncertainty-aware payday scenarios and emergency recovery planning remain future work. No new model was trained, no real users were tested, and no production integration was added.
