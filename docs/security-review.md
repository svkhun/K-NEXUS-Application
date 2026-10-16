# Security review — 2026-10-14

## Scope

Reviewed the React client, FastAPI routes, copied ONNX assets, dependencies, visitor state and Render deployment boundary. This is an anonymous public **synthetic-data demo**, not an authenticated banking system. The simulated verification endpoint does not establish identity or measure biometric liveness.

## Findings and fixes

| Finding | Change | Verification |
| --- | --- | --- |
| Visitors shared mutable global balances and reset state | Opaque cookie sessions scope all three preset accounts and pending transactions per visitor | Two independent HTTP clients; saving in one cannot change the other |
| Mutation routes accepted cross-site requests without a request token | Exact origin/host checks, Strict SameSite cookie, unpredictable session CSRF token on every POST, JSON only | Missing/wrong token, foreign Origin and text/plain rejected |
| Client could bypass a blocked destination through the high-value verification branch | Blocked destination policy runs before high-value step-up; risky synthetic recipients cannot be forced into the low-risk branch | A funded test session sending 50,000 to the blocked destination remains blocked |
| Old token could be reused across evaluation cycles or visitors | HMAC clearance binds amount, source, destination, hashed visitor binding, expiry and evaluation nonce; pending clearance consumed once, invalidated by cancel/reset | Cross-session, replay, altered token and replacement evaluation rejected |
| Repeated requests and concurrent clicks could debit twice | Per-session serialized requests and fingerprinted idempotency responses; different payload with reused key rejected; synchronous client in-flight guard | Same request concurrently executes once; payload collision returns 409 |
| Account fallbacks could silently affect the default account | Only three demo sources and five synthetic recipients accepted; unknown source rejected; self-transfer rejected | Unknown and same-account inputs rejected |
| Non-finite numeric validation could produce a server error | Finite amounts, two decimal places and caps; sanitized validation response never echoes raw values or tokens | NaN, sub-cent, negative and oversized amounts rejected |
| Unbounded request/state resources | 8 KiB streamed body limit, 120 requests/minute/session, one-hour TTL, 200 sessions, bounded pending/response cache and bootstrap rate limit | Oversized declared and chunked body, rate boundary and expired session tests |
| Incomplete browser security policy and unnecessary API surface | CSP, no framing, no MIME sniffing, no referrer, disabled camera/mic/payment permissions, API no-store, HSTS and Secure/HttpOnly __Host cookie in production; removed legacy API aliases and SecOps routes; disabled docs | HTTP header/cookie and route tests |
| Model checksum mismatch only logged | Fail startup on mismatch; CPU inference uses bounded thread counts | Both copied model SHA-256 checks pass |
| Vulnerable frontend build packages | Updated Vite/plugin and regenerated lockfile; removed unused inherited dependencies | npm audit and production build |

Initial npm audit reported 3 affected packages (2 high, 1 moderate): Vite, esbuild and source-map-js. These mainly affected build/development tooling. Primary advisories: [Vite](https://github.com/advisories/GHSA-fx2h-pf6j-xcff), [esbuild](https://github.com/advisories/GHSA-67mh-4wv8-2f99), [source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

## Deployment controls

The Docker image contains only built frontend assets, runtime source, pinned Python dependencies and synthetic data/models. It runs as a non-root user. The Blueprint generates the runtime secret instead of committing one. Git ignores local env files, environments, dependencies, caches and preview artifacts. Official GitHub Actions are pinned to immutable commits; workflow permissions are read-only. CI audits dependencies, exercises the HTTP boundary and builds/health-checks the production container.

## Practical limits

- Session state is process-local and intentionally temporary. Use exactly one worker and instance. Restart/deploy expires existing sessions.
- The last 32 successful POST responses are retained for idempotency within a session; very old keys fall out of that bounded cache.
- At most 200 active anonymous visitors and application-level rate limits are supported. Load/availability testing and upstream abuse controls are separate from these functional security checks.
- `style-src 'unsafe-inline'` supports React's dynamic chart styles; script execution is restricted to same-origin bundled code. Google Fonts are explicitly allowed for typography.
- Anonymous demo access is not real bank authentication or biometric verification. Do not send real account details or personal financial data into this prototype.
- Automated dependency scans report known advisories at scan time. Passing checks does not prove the absence of every vulnerability or constitute a penetration-test certification.

## Local verification

- `npm audit`: 0 reported vulnerabilities after updating the frontend dependencies.
- `pip-audit -r requirements.lock --disable-pip --no-deps`: 0 known vulnerabilities across the 22 pinned runtime distributions.
- Production frontend build passes with Vite 8.3.4.
- All 13 real HTTP security tests pass in the project's own environment, covering visitor isolation, request forgery, direct API bypass, concurrent replay, blocked high-value transfers, validation, cookie/header policy and fail-closed production configuration. `pip check` reports no broken requirements.
- Browser verification confirms the built UI boots its session and completes saving/recall through the guarded API without console errors.
- The local Docker daemon is unavailable, so the actual container build and production health check are implemented as a required CI step. Render deployment itself has not been created by this task.


## Feature expansion review

The added scenario, auto-saving and recall-mode mutations use the same session, exact-origin, CSRF, JSON/body/rate-limit and idempotency middleware. No public global account state or legacy SecOps endpoint was reintroduced. The new insights endpoint serves a cached, bounded, masked sample from the synthetic CSV; it does not accept an account lookup or query limit. Event history is limited to 50 records per persona within the existing session TTL, and profile responses only include that visitor's data. Downloaded receipts are explicitly labeled as demo records. Five-second verification is a client-side simulation and is not a biometric security boundary.

The backend now prevents manual/automatic sweeps from consuming projected funds reserved for upcoming debits and the emergency buffer. Undo and partial/all recalls conserve the combined main/vault balance. The expanded suite contains 19 passing tests (six product-invariant tests plus the existing 13 security tests).


## Savings update — 16 October 2026

The savings/Undo/automatic-cycle observations above describe the earlier revision. The current app uses explicit opt-in savings (THB 500 maximum per action) and standard explicit-amount withdrawals. See [source sync and verification](savings-sync-2026-10-16.md) for the current behavior.


## Risk-only cooldown boundary — 16 October 2026

The server stores recipient deadlines separately from pending confirmation tokens, preventing preference changes, cancellation/retry or amount changes from erasing an active pause. Authentication and confirmation both enforce readiness; token expiry starts at authentication after the wait. A new evaluation invalidates the source persona's previous review/token. Pending status omits nonces and tokens and remains session/persona-scoped. Ordinary transfers and blocked destinations retain their separate paths. See [the cooldown policy and tests](transfer-cooldown.md). The demo reset/restart still clears in-memory state; this is not a durable production bank hold.
