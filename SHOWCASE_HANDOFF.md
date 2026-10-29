# Application baseline handoff to Showcase

29 October 2026 · Asia/Bangkok. This file is in Application only; **Showcase was not edited**.

## Current facts to use

- Application local demo now uses `history28-min7-scenario-abstain.v1`:
  **HISTORY_MEAN → SCENARIO → ABSTAIN**. It is an explainable baseline, not a
  validated AI forecast. Local API/browser evidence is in
  `artifacts/baseline-integration/`; see `BASELINE_INTEGRATION_REPORT.md`.
- Default personas all use **SCENARIO, N0/28**: เมย์ ฿350/day, นนท์ ฿600/day,
  แพรว ฿300/day, excluding bills. Source `config/baseline-personas.v1.json`, version
  `synthetic-persona-assumptions.2026-10-29.1`. They have no verified current daily
  history. Do not call these measured averages or link them to legacy USER IDs.
- HISTORY_MEAN uses the 28 closed calendar dates and at least 7 complete known
  days. Zero is known, missing/partial is unknown. Integer satang/HALF_UP and N/28
  provenance are exposed. Browser HISTORY N7/28 screenshots use an explicitly
  labeled hand-authored acceptance fixture, not actual persona or research history.
- Live product adapter `live-intraday-next-day.v1` anchors at current balance/as-of,
  with 30 future days starting tomorrow. It assumes no additional spending today;
  posted-today debits already belong to current balance. It is separate from sealed
  midnight-issued forecasts. There is no reconstructed historical balance line.
- Forecast, plan, savings and transfer reviews share spending basis/version and
  the same outstanding bills through next payday, including next-month bills.
  Bill payments are copied projections, never actual settlement. Historical settled
  references classify spending only and do not reserve or pay a bill again.
- Unknown forecast means unavailable forecast-dependent capacity, graph gaps and
  reasons. Known balance/bill budgets and a separate explicit manual budget remain
  available. There is no automatic savings or money movement.
- TrustGraph `2026.10.27.1` model/embedding pair and checksums are unchanged.
  Application runtime constructs only its TrustGraph ONNX session.
  `flowsense_enabled=false` and the activation guard remain. Baseline switch is separate.

## Suggested copy

**TH:** “FlowSense ใน local demo ใช้ baseline ที่อธิบายที่มาได้: ค่าเฉลี่ยรายจ่ายที่ไม่ใช่บิล
จาก 28 วันปิดย้อนหลังเมื่อมีข้อมูลครบอย่างน้อย 7 วัน หากไม่พอใช้สมมติฐานรายวันแบบระบุ
version และหากไม่มีทั้งสองอย่างจะแสดงว่าข้อมูลไม่พอ โปรไฟล์เดโมทั้งสามใช้สมมติฐาน
สังเคราะห์ กราฟเริ่มจากยอดปัจจุบันและสมมติรายจ่ายตั้งแต่วันพรุ่งนี้ ยังไม่ใช่ validated
AI forecast หรือผลทดสอบความแม่นยำ 30 วัน”

**EN:** “The local Application uses an explainable baseline: a 28-closed-day
non-bill mean with at least seven complete known days, otherwise an explicit
versioned daily scenario, otherwise abstention. All three default personas use
synthetic scenario assumptions. The live projection starts from current balance
and assumes future spending from tomorrow. It is not a validated AI forecast.”

## Text and image changes needed in Showcase

1. Replace descriptions of the Application chart as “profile average” or ML output
   with the active policy/adapter and actual persona scenario source above.
   Legacy `avg_daily_spend` is a transaction mean including bills; it is not this
   baseline's measured daily burn.
2. Replace Application screenshots with the local evidence or capture new images
   from the deployed build **after a separate authorized release**. Identify images
   from this work as **local demo, synthetic data, 29 Oct 2026**.
3. Show method, N/28 when applicable, source/version, as-of and projection start.
   Preserve simulation labels in transfers and receipts. Show gaps/“ข้อมูลไม่พอ”
   rather than a zero/healthy/safe badge for ABSTAIN.
4. Remove claims that the old seven-day illustrative line is observed transaction
   history. Do not date-shift accepted research data into current demo history or
   present the HISTORY acceptance fixture as real persona coverage.
5. Keep ML research separate: Gate2 study `fs-gate2-20261028-01` did not pass and
   exported no qualifying package. `fs-direct-dev-20261028-01` is development
   research. Neither is the Application runtime predictor. Do not apply one-step
   MAE to the Application 30-day graph, infer GNN benefit, or claim field outcomes.
6. State local and deployed status separately. This work did not deploy anything;
   no production URL/process was verified. Accepted proposed.4/v2.1.1 data does not
   itself validate ML performance or authorize production activation.

Useful evidence images (Application paths):

- `artifacts/baseline-integration/browser-may.jpg`, `browser-non.jpg`,
  `browser-praew.jpg`: actual default persona source/value screens.
- `browser-scenario-chart.jpg`: default current-balance baseline chart viewport.
- `browser-history-chart.jpg` and `browser-history-dom.txt`: N7/28 **test fixture**,
  with source disclosure; not current real history.
- `browser-abstain-chart.jpg`, `browser-abstain-savings.jpg`: unavailable forecast
  and capacity, rather than zero. The chart image predates the final removal of an
  empty history toggle; the null/gap behavior is unchanged.

Do not describe backend/Node tests as browser tests. Final backend checks:
148 passed; frontend: 26 passed; production frontend build passed. Real loopback
API checks and bounded browser smoke are recorded separately. This is local
functional evidence, not deployment, bank integration or effectiveness evidence.

Rollback baseline with `FLOWSENSE_BASELINE_MODE=OFF`, keeping bill/retry/security
fixes and TrustGraph intact. No legacy FlowSense ONNX or silent zero fallback.
No Showcase change, training, export, commit, push or deployment was performed.

## Application release candidate — 30 October 2026

Application-only candidate verified in an isolated checkout: 148 backend and 26 frontend checks pass; clean Python/npm installation and production build pass. Runtime distribution preserves the approved manifest/model/embedding hashes, excludes training outputs and loads only TrustGraph. Production ASGI BASELINE and OFF checks pass separately from public/browser verification. Public deployment is still pending; see APPLICATION_RELEASE_REPORT.md. No Showcase write/deploy occurs in this task.
