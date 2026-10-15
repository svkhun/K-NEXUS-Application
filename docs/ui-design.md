# K: calm finance interface

The user's banking reference informs the dark green navigation, account cards and botanical accents. The cash-flow mockup informs the information hierarchy. The new layout uses warm paper and pastel surfaces rather than reproducing either reference.

## Shared visual language

- Deep green anchors the K brand and primary actions. Mint identifies cash flow and saving; sky blue identifies history; peach identifies outgoing funds/payday; lavender identifies protection and flexible reserves.
- `src/ui/pastel.css` supplies the shared palette, components and responsive rules across Home, Accounts, FlowSense, Transfer, results and the data lab. `FinanceDecor.jsx` contains lightweight, decorative SVG artwork with no external asset dependencies.
- Decorative artwork is hidden from accessibility APIs. Text, controls, focus rings and semantic risk states remain distinct from pastel backgrounds.
- Home places the chart across a full row and pairs recent activity with an illustrated saving prompt. Empty activity lists offer genuine actions rather than fabricated transactions.

## Cash-flow timeline

- Seven days of **synthetic** history, today's balance and 7/14/30 future days. Historical and future curves use different colors and line styles.
- Left axis: remaining balance. Right axis: outgoing funds. Expense bars combine daily spending and fixed commitments and never include salary as an expense.
- Today, the next salary inflow and the lowest projected balance **before** that salary are marked. The low-point summary excludes the previous history and the following salary cycle, regardless of the selected visible range.
- Pointer inspection, a keyboard/touch day slider and previous/next controls expose the exact selected day's balance, spending, commitments and inflow.
- The clock uses Bangkok time; the countdown targets midnight at the start of the API's simulated salary date. Scenario presets anchor the countdown to their simulated date. Neither the clock nor the countdown claims a connection to a live bank feed. Projection data changes only after an action or explicit refresh.
- On narrow screens, only the graph scrolls horizontally. Labels keep their size, and selecting a day reveals its marker. The surrounding page does not scroll horizontally. Summary tiles stack below the chart.

## Verification

`npm run test:ui` checks payday minimums, visible-range independence, expense totals, negative/zero axes and timezone/simulation countdowns. This suite runs in CI alongside the existing API/security tests and production build. Browser QA covers all four pages at 320px and 768px, the timeline at 390px, and the desktop layout at 1440px.
