# Risky transfer cooldown — 16 October 2026

## Product decision

The user clarified that cooldown applies before risky transfers, not savings withdrawals. They reported that most survey respondents accepted waiting and originally proposed 15 minutes. The survey responses and duration-specific distributions were not supplied for this task. We retain **15 minutes, enabled by default**, as a prototype hypothesis to test, not an empirically optimal duration, a proven fraud-prevention outcome or a Thai regulatory requirement.

The [FCA's review of APP fraud controls](https://www.fca.org.uk/publications/multi-firm-reviews/anti-fraud-controls-complaint-handling-firms-focus-app-fraud) supports testing tailored risk warnings and appropriate intervention; it does not establish a 15-minute standard for this application. The [Bank of Thailand's scam guidance](https://www.bot.or.th/th/satang-story/fraud/call-center.html) describes pressure to transfer and encourages independent verification. These inform the waiting screen's practical checks. No claim is made that staff investigate the account while the timer runs.

## Scope and settings

- Low-risk routine transfers retain the original immediate demo execution.
- A large transfer alone retains simulated authentication without a cooldown. A large **risky** transfer follows the risk branch, so the amount gate cannot bypass the pause.
- The blocked demo destination remains blocked. Expiration, settings and authentication cannot enable it.
- The optional 15-minute pause applies to risky transfers (`CRITICAL_ANOMALY` in the existing synthetic engine). It is enabled per visitor/persona by default. A disclosure on the transfer page shows the active setting; switching it off requires a second explicit confirmation.
- Turning it off affects new risky transfers without an already-started hold for that recipient. It does not turn off risk evaluation, explanations, simulated authentication, final confirmation or destination blocking.
- An active recipient hold survives preference changes, cancellation/retry and amount changes until its original expiry. A new evaluation invalidates that source's previous pending review and token; it reuses an existing recipient deadline rather than resetting or bypassing it. Successful execution clears that hold, so the next risky transfer starts a fresh pause if enabled.

## Timing and transaction safety

The deadline is server time plus 900 seconds. Both simulated authentication and final transfer execution check the server deadline. The client uses server time plus monotonic elapsed time to display a countdown; changing the browser clock does not authorize execution. It refreshes status on focus/visibility and every 30 seconds while the review screen is active.

Only one pending review is retained per source persona. Reload fetches its sanitized evaluation, source, destination, amount and current timing. A home banner returns to that review. The client does not persist clearance tokens or alter balances. The waiting screen displays the amount, receiver, deadline, countdown, cancellation and independent verification guidance. The result panel is revealed after evaluation on phones; detailed risk signals remain expandable.

The pending review lasts until ten minutes after the waiting deadline (two minutes for the existing large-value-only gate). Authentication issues a session/amount/destination/nonce-bound token valid for two minutes from authentication, extending an almost-expired review to cover that token window. Expired authentication can be repeated while the review is active. Expired reviews must be evaluated again. Completing a timer does not debit money: the user must authenticate and explicitly confirm. Cancellation remains available during the wait.

All preferences and state-changing calls retain the existing exact-origin, CSRF, strict request schemas, visitor isolation, rate/body limits, per-session serialization and idempotency controls. No public timing-override endpoint is provided.

## Prototype limits and evaluation

Balances, scores, recipients and authentication are synthetic. A timer creates reflection time; it does not verify a real payee or protect against account takeover by itself. Session storage is in memory and expires after one hour or a service restart/deployment. The demo's explicit account reset clears pending reviews, recipient holds and preferences; a production system would need durable transaction holds and policy-controlled changes.

Before changing 15 minutes, test actual behavior with target users: comprehension, voluntary cancellations after checking, legitimate-payment completion, preference opt-outs and frustration. Survey acceptance alone does not establish scam reduction. Changing a security setting in a real banking product would also need genuine authentication and a reviewed bank policy.

## Verification

- 41 Python regressions include seven cooldown tests: exact deadline, no early authentication/debit, final-confirmation enforcement, token renewal/replay, amount change/cancel/retry, settings privacy/CSRF, risk-vs-value ordering, blocked destinations and restored/expired reviews.
- 13 frontend logic tests include server-anchored countdown boundaries, malformed timing failing closed, and timer formatting.
- Browser QA checks mobile countdown, settings confirmation, reload restoration, cancellation, ordinary execution, the disabled optional-pause flow with simulated authentication, and responsive wrapping. Completion at the real 15-minute boundary is covered with controlled server time in API tests.
