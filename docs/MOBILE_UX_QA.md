# Mobile UX verification — 19 October 2026

## Changes

- Replaced the K+ wordmark with an original K NEXUS vector mark, using white lettering, a green connecting stroke, and the existing navy/teal palette. Updated the favicon and included `public/k-nexus-logo.svg` for reuse.
- Fixed the negative margin that placed the savings explanation against the budget banner. Rewrote the Thai copy to explain that moving savings does not increase the combined balance and that ordinary withdrawals remain available.
- Replaced the transaction hub's single changing card and decorative dots with two real scroll-snap account slides. Native touch scrolling, account selectors, arrow buttons, keyboard navigation, and page indicators all refer to the same selected account. Resizing preserves the selection, and reduced-motion preferences disable animated navigation.
- Increased header, carousel, chart, tutorial, and dismiss controls to at least 44 CSS pixels where changed. Removed the raised middle navigation button that extended over content.
- Improved Thai text sizes, spacing, balance layouts, narrow account selectors, savings actions, transfer settings, safe-area spacing, and short landscape dialogs. Amount entry retains decimal keyboards; small select/input fields use at least 16px to avoid focus zoom on supporting mobile browsers.
- Fixed account overview columns inheriting 88% carousel widths at tablet/desktop sizes.
- Opening mobile search focuses the input; Escape closes it.

## Verified locally

Production build served by the local API, with real session and CSRF handling, in headless Chrome with touch/mobile emulation:

- Seven widths: 320, 360, 390, 430, 768, 1024, and 1440 CSS pixels.
- Seven screens at every width: home, transactions, savings, profile, spending plan, accounts/chart, and transfer. No document-level horizontal overflow in these 49 checks.
- Actual browser touch events swipe accounts in both directions without opening them. A vertical gesture preserves the selected account. Selector buttons and keyboard Home agree with the visible slide.
- Rotation from portrait to landscape preserves the selected savings account; reduced-motion navigation works.
- Search focuses and navigates; enabling savings, saving 100 baht, and withdrawing 100 baht complete against the local simulated API.
- All eight tutorial steps fit the phone viewport, including traversal into transfer review.
- Transfer review opens across all seven widths. Risk warnings, bank-help view, returning to the warning, cancellation, and blocked-recipient behavior work at landscape 844×390, narrow 320×568, and short 390×500 viewports. Blocked recipients have no confirm-transfer button.
- No JavaScript page errors in the responsive walkthrough.
- `npm run build`, all 16 `npm run test:ui` tests, and `git diff --check` pass.

Local screenshots and browser-run scripts/results are under the ignored `artifacts/` directory. They contain synthetic account values only.

## Limits

These checks cover browser emulation and the local prototype. Physical iOS Safari, Android browsers, actual software keyboards, assistive technologies, slow/interrupted connections, and the hosted release still need device/release verification. A short viewport simulates reduced space but does not prove real keyboard behavior. No deployment or production financial-readiness claim is made.
