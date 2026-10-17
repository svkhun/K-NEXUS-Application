# Risky transfer cooldown — 16 October 2026

## Product decision

The user clarified that cooldown applies before risky transfers, not savings withdrawals. They reported that most survey respondents accepted waiting and originally proposed 15 minutes. The survey responses and duration-specific distributions were not supplied for this task. We retain **15 minutes, enabled by default**, as a prototype hypothesis to test, not an empirically optimal duration, a proven fraud-prevention outcome or a Thai regulatory requirement.

The [FCA's review of APP fraud controls](https://www.fca.org.uk/publications/multi-firm-reviews/anti-fraud-controls-complaint-handling-firms-focus-app-fraud) supports testing tailored risk warnings and appropriate intervention; it does not establish a 15-minute standard for this application. The [Bank of Thailand's scam guidance](https://www.bot.or.th/th/satang-story/fraud/call-center.html) describes pressure to transfer and encourages independent verification. These inform the waiting screen's practical checks. No claim is made that staff investigate the account while the timer runs.

## Scope and settings

- Routine transfers now open a no-debit review with the plan impact and an explicit final confirmation. They require neither simulated authentication nor a timed pause. This supersedes the previous immediate execution behavior; see [transfer planning](transfer-planning.md).
- A large transfer alone retains simulated authentication without a cooldown. A large **risky** transfer follows the risk branch, so the amount gate cannot bypass the pause.
- The blocked demo destination remains blocked. Expiration, settings and authentication cannot enable it.
- The optional 15-minute pause applies to risky transfers (`CRITICAL_ANOMALY` in the existing synthetic engine). It is enabled per visitor/persona by default. A prominent mint settings card on the transfer page exposes the status and switch immediately; switching it off requires a second explicit confirmation.
- Turning it off affects new risky transactions. An already-active transaction keeps its original policy until cancelled or replaced. Risk evaluation, explanations, simulated authentication, final confirmation and destination blocking remain enforced.
- Cooldown belongs to the pending transaction, not to a separate recipient hold. Rechecking the same active source/destination/amount retains that transaction's deadline while invalidating its old confirmation token. A different destination or amount replaces the review and uses current settings.
- **Cancel means the transaction and its timer end.** A new transaction after cancellation reads current settings: disabled means no cooldown; enabled means a fresh full 15 minutes, even for an identical receiver and amount. No hidden timer survives cancellation.

## Timing and transaction safety

The deadline is server time plus 900 seconds. Both simulated authentication and final transfer execution check the server deadline. The client uses server time plus monotonic elapsed time to display a countdown; changing the browser clock does not authorize execution. It refreshes status on focus/visibility and every 30 seconds while the review screen is active.

Only one pending review is retained per source persona. Reload fetches its sanitized evaluation, source, destination, amount and current timing. A home banner returns to that review. Routine review restoration supplies a session-bound token with purpose `review`, which cannot authorize a risky transfer. Risky status never returns an authentication token. The client does not persist tokens or alter balances. The waiting screen displays the amount, receiver, deadline, countdown, cancellation and independent verification guidance. Evaluation results open in a native modal instead of scrolling the document. It is centered on desktop and fills the phone viewport, with internally scrolling content, a visible header/close control and cancellation in the footer. Native modal isolation, explicit Tab wrapping, Escape handling, body-scroll locking and focus restoration support keyboard use. Detailed risk signals remain expandable.

Closing the modal, pressing Escape or returning to the form leaves the pending transaction intact; these actions do not cancel it. The form shows a resume/cancel row. The modal's settings action closes it and focuses the visible switch. A separate explicit cancellation action ends the transaction. Errors from API actions remain visible inside the modal.

The pending review lasts until ten minutes after the waiting deadline (two minutes for the existing large-value-only gate). Authentication issues a session/amount/destination/nonce-bound token valid for two minutes from authentication, extending an almost-expired review to cover that token window. Expired authentication can be repeated while the review is active. Expired reviews must be evaluated again. Completing a timer does not debit money: the user must authenticate and explicitly confirm. Cancellation remains available during the wait.

All preferences and state-changing calls retain the existing exact-origin, CSRF, strict request schemas, visitor isolation, rate/body limits, per-session serialization and idempotency controls. No public timing-override endpoint is provided.

## Prototype limits and evaluation

Balances, scores, recipients and authentication are synthetic. A timer creates reflection time; it does not verify a real payee or protect against account takeover by itself. Session storage is in memory and expires after one hour or a service restart/deployment. The demo's explicit account reset clears pending reviews and preferences; a production system would need durable transaction holds and policy-controlled changes.

Before changing 15 minutes, test actual behavior with target users: comprehension, voluntary cancellations after checking, legitimate-payment completion, preference opt-outs and frustration. Survey acceptance alone does not establish scam reduction. Changing a security setting in a real banking product would also need genuine authentication and a reviewed bank policy.

## Verification

- 44 Python regressions include ten cooldown tests: exact deadline, no early authentication/debit, final-confirmation enforcement, token renewal/replay, same-review retention, cancellation followed by a disabled or enabled new transaction, amount replacement, settings privacy/CSRF, risk-vs-value ordering, blocked destinations and restored/expired reviews.
- 13 frontend logic tests include server-anchored countdown boundaries, malformed timing failing closed, and timer formatting.
- Browser QA checks visible settings, popup sizing at phone/desktop widths, close/Escape vs cancellation, keyboard focus, reload restoration, and the exact reported sequence: enable → risky transfer → disable → cancel → new identical transfer with no inherited timer. Normal transfers and authentication retain their existing paths. Completion at the real 15-minute boundary is covered with controlled server time in API tests.
