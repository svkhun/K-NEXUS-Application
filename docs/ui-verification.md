# Pastel interface verification

- Production build: `npm run build`.
- Chart logic: `npm run test:ui` — five cases cover the pre-payday low point, range selection, total expense bars, deficit/zero axes and Bangkok countdowns.
- Browser: Home, Accounts, FlowSense and Transfer have no document-level horizontal overflow at 320px and 768px. At 390px the chart alone scrolls, and selecting the last day reveals its point automatically.
- Interactions: 7/14/30-day ranges, synthetic history toggle, outgoing-bar toggle, keyboard day selection, automatic graph reveal, saving recommendation and Undo.
- Visual review: desktop dashboard, tablet transfer, mobile account timeline and saving/recall forms. The K logo and independent-prototype labels remain visible.
- No new external assets or runtime dependencies. API, model and security behavior are unchanged.

The [design notes](ui-design.md) describe the shared palette and chart semantics. Browser screenshots are saved under the ignored `artifacts/` directory for local review.


## Savings update — 16 October 2026

The savings/Undo/automatic-cycle observations above describe the earlier revision. The current app uses explicit opt-in savings (THB 500 maximum per action) and standard explicit-amount withdrawals. See [source sync and verification](savings-sync-2026-10-16.md) for the current behavior.
