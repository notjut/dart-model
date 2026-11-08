# Darkhorse dashboard redesign · 8 November 2026

## What changed

Picks open first. A compact original Darkhorse masthead, dedicated scoreboard, sticky Picks / Live / Parlays / Results navigation, and keyboard-accessible More menu replace the competing navigation layers. Featured Seabiscuit and other outright-underdog picks show price, model chance, projected score, strongest positive **actual core-model contribution**, kickoff in Eastern Time, provider and retrieval time without opening a report. The existing +170 Seabiscuit rule is unchanged. A contribution is an explanation of the fitted forecast, not a new bonus or a guarantee.

The full slate uses a responsive grid with day, conference, team, odds-tier and sorting controls. Each game leads with the moneyline selection. Projected score is immediately followed by the cover and O/U picks. Live/final scores have a separate tab. Missing, expired, review-required and overdue states keep the original eligibility safeguards. Empty days show the next loaded slate and a route to saved results.

The betslip remains a research tool. Its storage keys, ticket schema, limits, selection/conflict rules, settlement and payout mathematics are unchanged. Saving, tracker, exports, suggested parlays, Sniper Sauce, score explorer, and matchup research remain available. The drawer has focus trapping, Escape dismissal, focus return and an inert background. It never places a bet.

## Branding and CSS ownership

- `darkhorse-brand.css` owns identity: background #090e0d, ink #f0f0e6, muted #a9b9b3, line #31433b, mint #78f5c6, gold #e9c883, original wordmark/horse and ///.
- `gameday.css` owns the dashboard: background #080c12, ink #f2f6f8, line #29353f, mint #80f7da, gold #f9d88c. Transparent gradients derive from these same colors.
- `style.css` owns shared controls, report layout and accessible base styles. `dart-theme.css` and `darkhorse.css` remain in the repository but are no longer layered over the dashboard.
- Anton is the display/wordmark face; Inter is UI; Barlow Condensed remains a fallback. The original PNG is unchanged. WebP derivatives are identical source artwork at display sizes. WOFF2 subsets total 136,804 bytes.
- Canonical, Open Graph and Twitter large-image tags use the branded 1200×630 PNG. `#matchup/GAME_ID` links directly to a report; older loaded games fall back to their saved slate.

## Loading and data integrity

`picks-bootstrap.json` is a generated view of the canonical data, not an independent feed. The existing package step derives it from data.json/model.json. It preserves every forecast's margin, total, uncertainty, contribution and review flag, and retains completed scores needed by saved tickets. All canonical endpoints remain. No model weights, forecasting equations or source data were edited.

History, player facts, upset-history and full research profiles are outside the initial blocking fetch. Research and specialist tools load on demand with loading/error states. Forecast/odds requests start concurrently; started-game data is fetched once. Date formatters are reused, calendar counts are computed once, and the eligible market pool is reused only within a synchronous render so later actions still recheck eligibility.

## Regression results

- 84 Python tests passed, including three new tests verifying bootstrap forecast parity, completed-score preservation and canonical research availability.
- Existing JavaScript suites passed: freshness/rolling week, result records, Seabiscuit qualification, QB/availability eligibility, HTML safety, rankings, opponent adjustment, started games, calendar, 12-leg constraints, mixed-market tickets, persistence, settlement, live-score parsing, and Sniper correlated scenarios/readiness.
- Syntax checks passed for changed application scripts.
- Browser checks: 360px and 390px filters; conference/search/day/odds/sort; More Enter/Escape; betslip Escape/focus return; saved ticket survives reload; download creates the original text slip; matchup deep link opens a real report; cover and O/U appear directly after score; Sniper lazy-loads; current empty day and next slate; actual final scoreboard; injected failed forecast request shows a retry state without made-up data. Pregame visuals used unchanged real saved Nov 7 inputs with a **local-only test clock**. No test clock or QA routes are included in the public package.
- Existing unit tests cover live/final/postponed, expired prices, missing probabilities, review blocks and missing-data states. No application console errors were observed in healthy browser flows (browser-extension metadata errors are external to the site).

## Measured checks and limits

Local Chrome preview, warm cache, no CPU/network throttling. These are lab observations, **not a claim about real-user p75 Core Web Vitals or a full WCAG certification**.

| Check | Observed |
|---|---:|
| 390×844 pregame LCP | 1.140 s |
| 390×844 pregame CLS before interaction | 0.0021 |
| 390×844 maximum observed filter/menu event duration | 112 ms |
| 1440×900 pregame LCP | 0.440 s |
| 1440×900 pregame CLS | 0.0012 |
| First featured card bottom, mobile / desktop | 722 / 794 px |
| Current empty-state bottom at 390×844 | 665 px |
| Horizontal document overflow, 360 / 390 / 1440 | None |
| H1 elements | 1 |
| Visible text under 12px / controls under 44px on tested picks view | 0 / 0 |
| Dashboard ink / muted / mint / gold contrast against background | 18.02 / 9.59 / 15.15 / 14.21 : 1 |

Initial JS is 136.2 KB uncompressed; initial CSS is 36.6 KB; all WOFF2 fonts are 136.8 KB. The initial JSON view and quotes total 564.6 KB raw / 62.3 KB gzip; JS is 50.3 KB gzip. The original 845 KB mark is replaced in page display/favicon by a 5.2 KB derivative. Cached transfer measurements cannot establish the cold 1 MB first-screen target. A production cold-cache/throttled audit and real-user INP measurement remain necessary to certify the requested performance budgets; the observed event duration is only a responsiveness proxy. Earlier development runs exceeded responsiveness/shift targets while hot-reloading; the stable final observations above followed removal of duplicate hidden-history rendering and reuse of the date formatter.

## Screenshots

[Before: mobile](darkhorse-before-mobile.jpg) · [After: mobile pregame](darkhorse-after-mobile-picks.jpg) · [After: honest empty day](darkhorse-after-mobile-empty.jpg) · [After: desktop](darkhorse-after-desktop.jpg)

Pregame screenshots replay saved inputs only for layout verification; the ticker still displays actual received final scores. They are not current betting recommendations. The live site always uses the real clock.
