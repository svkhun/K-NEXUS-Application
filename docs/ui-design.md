# K: mobile banking experience

The 16 October 2026 revision separates the home overview from the daily budget editor and starts the layout at phone widths. The previous large summary was rendered on both pages, obscuring their different purposes. The previous typography pass also enlarged small roles indiscriminately across five cascading stylesheets. The replacement assigns sizes by role in one stylesheet.

## Reference research and application

- [K PLUS official product page](https://www.kasikornbank.com/th/kplus/pages/index.aspx): important services on the home screen and access to spending/budget information. Its official phone image groups frequent transactions and accounts into distinct regions. Applied here as a compact wallet overview with four quick actions.
- [MAKE official Cloud Pocket guide](https://makebykbank.kbtg.tech/features/cloud-pocket): distinguish allocated money using named pockets, individual balances and purpose-specific cards. Its published phone screens use moderate corner radii and a bottom navigation. Applied here as separate main/savings balances, a mint daily budget card and contextual pastel surfaces.
- These are design interpretations of public product pages and images, not access to either app's internal design system. The K identity and prototype disclaimer remain independent of their branding.

## Shared visual language

- Deep green anchors the K brand and primary actions. Mint identifies cash flow and saving; sky blue identifies history; peach identifies outgoing funds/payday; lavender identifies protection and flexible reserves.
- `src/ui/banking.css` supplies the only imported stylesheet, including palette, layout, components, mobile navigation, risk states and breakpoints. The five superseded stylesheets were removed. `FinanceDecor.jsx` supplies decorative SVG artwork; no bank artwork is bundled.
- Decorative artwork is hidden from accessibility APIs. Text, controls, focus rings and semantic risk states remain distinct from pastel backgrounds.
- Home: total balance, account allocation, quick actions, today's remaining allowance, forecast/saving/risk entry points and real session activity. It does not render a model forecast panel or budget editor.
- Plan: the budget input, slider, presets and reserve result appear first. Model spending estimates follow, and the formula/bills are under an expandable detail. There is no copy of the home allowance card.
- Accounts: full timeline, accounts, commitments and graph/data experiments. Advanced scenarios are expandable and show the currently selected scenario.
- Body text uses 14px, controls 13–14px, secondary explanations 12px, annotations 11px, main titles 23–28px, and monetary values sized to the task. Editable financial inputs stay at least 16px on phones. Thai text uses natural height and line spacing, with no fixed text containers. Main actions, navigation and data input have touch areas of at least 44px.
- Empty activity lists offer genuine actions rather than fabricated transactions. Settings for personas, reset and demo context are grouped in one disclosure instead of occupying the first screen.

## Cash-flow timeline

- Seven days of **synthetic** history, today's balance and 7/14/30 future days. Historical and future curves use different colors and line styles.
- One baht scale at the left covers both remaining balances and expense bars. Expense bars combine daily spending and fixed commitments and never include salary as an expense.
- Today, the next salary inflow and the lowest projected balance **before** that salary are marked. The low-point summary excludes the previous history and the following salary cycle, regardless of the selected visible range.
- Pointer inspection, a keyboard/touch day slider and previous/next controls expose the exact selected day's balance, spending, commitments and inflow.
- The clock uses Bangkok time; the countdown targets midnight at the start of the next simulated salary date. Every scenario uses the current Thai calendar date. The interface refreshes after actions, explicit refresh and a detected Thai day change; it does not imply a live bank feed.
- On narrow screens, only the graph scrolls horizontally. Labels keep their size, and selecting a day reveals its marker. The surrounding page does not scroll horizontally. Summary tiles stack below the chart.

## Verification

`npm run test:ui` checks budget simulations, model spending aggregation, payday minimums, range independence, expense totals, axes and Bangkok time. CI also runs API/security tests and a production container check. UI verification targets Home and Plan at 320/390px, every task at phone width, expanded formula/scenario controls, long/invalid amounts, transfer risk/cancel, saving/undo, privacy, and desktop/tablet breakpoints. This is developer QA, not a study with real banking customers.

Narrow-screen inspection found the demo settings panel could extend outside the screen when its trigger wrapped. The phone panel now anchors to the full intro width, while tablet/desktop use a trigger-anchored panel. At 320px the measured panel is inside the page (left 12px, right 293px), with no horizontal document scroll.
