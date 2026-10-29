# Application baseline release — 30 October 2026 (Asia/Bangkok)

**CANDIDATE_VERIFIED — publication pending.** This section is the reviewable pre-publication snapshot. Final public/deploy evidence will be appended separately without guessing a final commit SHA.

## Target and public version before release

- Workspace `My Workspace` / `tea-dak0nuuq1p3s739rgbj0`, previously confirmed in the Showcase release evidence; connected Render account confirms the same workspace.
- Application service `k-nexus-app` / `srv-dba8c061egvs739onubg`, URL <https://k-nexus-app.onrender.com/>. Git source confirmed by Render: `https://github.com/svkhun/K-NEXUS-Application`, branch `main`. Local origin still has its previous repository name `K-NEXUS-Web`; the confirmed canonical remote resolves to the same HEAD.
- Previous live commit `4eb7821e7ad776fa90c5fd2cf44616836f9d0ec2`, deploy `dep-dbap850ae00c73a0rmog`, status `live`. Public health returned only the old synthetic-demo `4.0.0` fields, without baseline/package identity; `/release.json` returned 404. Root HTTP 200, index SHA-256 `5385a87e1dfc75b681866a33f0d83df8095f43b30259beb6e373ed3ddf58ab47`. The new local baseline is not live yet.
- Docker, free instance, Singapore, one instance, health `/api/v2/health`, Dockerfile `./Dockerfile`, empty Docker command override; actual command is Dockerfile `python run.py`. Auto-Deploy is `yes`, trigger `checksPass`.
- Legacy service also tracks main with automatic deploys. Therefore **do not push main**. Publish `codex/application-baseline-release-20261030` and change only this Application service's branch after verification. Do not modify, trigger or deploy legacy/Showcase. No new paid resources.

## Release scope and files

The original HEAD/index/staged entries are preserved. Candidate checkout is isolated under `artifacts/application-release-20261030/checkout`. Files are copied by an explicit reviewed inventory, never by whole-tree copy, whole-tree stash, reset/clean, or `git add .`.

`docs/application-release-20261030/FILES.json` lists each included file, SHA-256 and reason. Accepted pending work is released together: baseline selector/config, versioned live adapter, bill instances/partial payments/month rollover, backend forecast/plan/savings/transfer consumers, UI/null disclosures, command journal, session/idempotency/security fixes, approved TrustGraph runtime pair, and the exact schema/acceptance fixture dependencies needed by regressions. The schemas/fixture helpers are existing acceptance dependencies; this is not another contract/ML/research audit.

Packaging-only additions: Docker now copies `config/` and only the two CSV files actually used for runtime persona/profile and recipient policy metadata. `npm run build` creates a source/asset fingerprint; backend serves `/release.json` and the built public logo. Production baseline default remains OFF; only the target demo is configured BASELINE. Dev requirements now declare `jsonschema==4.26.0`, avoiding the prior read-only Showcase-venv dependency.

The immutable package manifest is unchanged. Following the user's explicit runtime-only selection, the release includes its manifest, `flowsense.onnx` (hash verification only), `trustgraph.onnx` and `trustgraph_embeddings.csv`. The serving loader verifies these exact required files against the approved manifest and preserves full integrity mode for callers holding the complete package. Training `.pt`/`.txt`, parity arrays, evaluation outputs, research datasets, screenshots, credentials and `.env` files are excluded from newly added release files. Existing tracked research CSVs are inherited from the old repository but are not Docker runtime inputs. No model, threshold or contract semantics changed.

## Fresh verification of this candidate

| Check | Actual new result |
|---|---|
| Clean frontend installation | PASS, `npm ci --no-audit --no-fund`, 22 packages in an initially empty candidate node_modules |
| Clean Python installation | PASS, new Python 3.13.1 venv, pinned requirements-dev/runtime and jsonschema installed; `pip check` passes |
| Backend release regressions | 148 PASS, 0 FAIL/errors/SKIP/TIMEOUT; each file bounded to 90 seconds |
| Full research-package/legacy parity tests | 3 NOT_RUN, explicitly listed by release runner; these require intentionally omitted research artifacts or legacy inference. Their assertions remain unchanged. New runtime integrity tests cover the deployed distribution |
| Frontend Node tests | 26 PASS, 0 FAIL/SKIP |
| Production frontend build | PASS; index plus JS/CSS/favicon/logo generated in isolated candidate |
| Dependency audits | npm audit and pip-audit PASS, no reported vulnerabilities |
| Production ASGI serving and financial protocol | PASS for 3 fresh persona sessions: SCENARIO N0/28 350/600/300, source/version/as-of/tomorrow projection, common spending basis, preference no debit, save/replay/withdraw, stale-review rejection, normal transfer/replay one debit, unmodified cooldown rejection/cancel, blocked policy, CSRF |
| Production OFF rollback process | PASS, 3 fresh sessions: ABSTAIN/null future/capacity, rejected sweep, explicit withdrawal available; only TrustGraph session |
| FlowSense activation startup guard | PASS, attempted enabled config rejected before any model session was created |
| HISTORY_MEAN / no-scenario ABSTAIN acceptance | PASS within isolated baseline regression fixtures; hand-authored declarations, not public observed history |
| Local Docker daemon / Linux container | NOT_RUN locally: Docker named pipe unavailable; CI container verification remains pending |
| Public HTTP and deployed browser | PENDING until release is live; ASGI/Node are not browser evidence |

Evidence is under candidate `artifacts/application-release/`: checks.json, per-file logs, frontend-tests.log, build.log, serving-BASELINE/OFF.json and logs, package-integrity.json, audit logs, clean-python-freeze.txt. Commit summary evidence is in `docs/application-release-20261030/`. Initial runner import errors and missing two helper/fixture dependencies were fixed without changing financial formulas or existing assertions; retained initial logs are not counted as passes. A Starlette/httpx deprecation warning does not fail these tests.

## Package identity and model-session scope

- Manifest SHA-256: `d73fd16f7f4e304c6a00900b1771d09c09aa6136f49b98a951409200d1931b4a` (original pin).
- TrustGraph ONNX: `e290222ed939caabf5455d4aac17e1a7f680c9d395ebabb99e057367c449efe3`.
- TrustGraph embedding: `3a5f0f348ae3578c65bb1ef2ad661e32adb7e7907bb929fbd26d3101ac136ab0`.
- FlowSense ONNX: `5d96f506ea16ef87dc2c40fa3cbbc426557d62583c4e28deae6458e9edc5a186`, checked as bytes only; no FlowSense model session is created.
- **3/3 deployed artifact hashes match**, plus manifest pin; not a new 13/13 full-package check. Package `2026.10.27.1`, threshold 0.5, startup loaded_models exactly `['trustgraph']`, flowsense_enabled=false and activation startup guard retained.

## Build, configuration and final identity

Release ID `application-baseline-20261030.1`. Candidate source SHA-256 `6aa62dfef27d2846ae166bb48ac40c318d04480322fe58ebba24046976bb104b`; all 74 source/build input hashes match the staged Git blobs. JS `assets/index-W3GDJnEW.js`, CSS `assets/index-CRdY__IR.css`. `/release.json` separates SHA-256 of actual source bytes and built assets from final `deployed_commit`, supplied at runtime by Render's documented `RENDER_GIT_COMMIT`. It contains only relative source names/hashes and public configuration state; no machine paths, secrets or visitor data. It is no-store. Missing platform revision is null, never guessed. Build output does not embed its own final commit.

Actual target-only config merge: `FLOWSENSE_BASELINE_MODE=BASELINE` and `PUBLIC_ORIGIN=https://k-nexus-app.onrender.com`. Existing ENVIRONMENT/HOST/proxy/DEMO_SESSION_SECRET are preserved without exposing their values. Automatic approval review rejected the broader wildcard proxy mutation; the safer two-key merge succeeded. Exact origin/host validation, __Host secure/HttpOnly/SameSite strict cookie, CSRF/session-token binding, cooldown and blocked policy remain active. Dashboard/connector is this existing service's configuration source; no Blueprint is applied and inherited render.yaml is not a record of current service branch.

Commit/deploy ID, terminal status, final source identity and active config are PENDING. Do not infer a live release from a successful push/trigger. Auto-Deploy must be observed; never trigger another deploy while the same commit is building/deploying.

## Financial and session limitations

Policy `history28-min7-scenario-abstain.v1`, adapter `live-intraday-next-day.v1`. Scenario version `synthetic-persona-assumptions.2026-10-29.1` is an explicit non-bill engineering assumption, not measured history. HISTORY requires at least 7 complete known dates among 28 closed Bangkok dates; known zero counts, unknown/partial/missing do not become zero. No USER/ACC inference, date shifting, history upload/debug endpoints, or research ledger import.

Posted-today is already in current balance; future burn begins tomorrow. Shared consumers reserve outstanding bills until before next payday, including next-month bills; projections use copies and do not settle bills. Session changes require renewed transfer review. ABSTAIN keeps forecast-dependent amounts null and preserves independent deterministic budgeting/explicit withdrawals.

All money is synthetic. Transfers debit the sender's session only and do not prove receipt at a destination. State/idempotency are process-local, one worker, one-hour sessions, bounded 200 active sessions. Retry replies retain 32 entries/2 MiB, command tombstones up to 512; evicted results fail closed instead of debit again. Session expiry/restart loses state/journal; this is not durable banking exactly-once processing. Session creation/rate limits and free-tier cold starts can delay QA. No existing user's session is reset; automated QA creates fresh cookie jars and changes only those synthetic sessions.

## Remaining public QA and rollback

After live, run `python scripts/verify_release_public.py --base https://k-nexus-app.onrender.com --expected-commit <verified-SHA> --expected-source <verified-source-hash> --output artifacts/application-release/public.json`. Browser checks must use the public URL in fresh browser context: all personas' source/value, plan/chart/savings/transfer surfaces, narrow layout, keyboard and console. Public history-write fixtures are prohibited. Risky completion after the unmodified 15-minute cooldown is NOT_RUN unless actually exercised; do not reduce the cooldown.

First rollback option: set only target `FLOWSENSE_BASELINE_MODE=OFF` and deploy the **same fixed release**. Verify `/release.json`/health OFF, TrustGraph-only sessions and ABSTAIN/null output. Keep bill/retry/security fixes and original TrustGraph pair. Do not revert to the old live commit: it predates these financial/idempotency/package fixes. A full deployment rollback needs a separately reviewed fixed release; no silent FlowSense fallback, force push or original-worktree reset. A process restart resets visitor demo state.

## Publication correction — final checks after fixture inventory repair

Initial commit `fa2b64b55db6005e02d181d53f4d271f50f52b0a` reached Application live via service_updated after selecting the branch, but CI run `40925939341` failed: 147 PASS and one FileNotFoundError for two sealed forecast-request-example.json fixtures omitted while pruning producer outputs. The first 148-PASS table above predates that pruning; it does not establish the incomplete initial commit's final CI result. No financial formula/assertion/model bytes changed. Both exact fixture dependencies are restored, and the bounded local runner now passes 148/148 again; its error logs also print on failure for CI diagnostics. Full corrected CI/container/public verification remains pending below.

The baseline/origin connector merge automatically initiated an intermediate deployment of the old main commit, and the branch settings update queued the release. No manual trigger was used; no claim that checksPass gated that settings-triggered rollout is made. The final deploy and all intermediate terminal statuses will be recorded after verification.

Original working-tree preservation check: 627 explicitly inventoried files match their before hashes; original HEAD and index entries match. Original source/dist were not built or edited. Only reports/handoff requested for this release will be written back after verification.
