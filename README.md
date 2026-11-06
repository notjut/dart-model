
### Sniper Sauce player props (experimental)

The **Sniper Sauce** tab lists upcoming games, recorded player production,
matchup-adjusted projections, and historical final-margin scenarios. The existing
`daily-refresh.yml` workflow runs `scripts/sniper_props.py`; no second updater is needed.

To connect posted NCAAF prop lines, add a repository Actions secret named
`ODDS_API_KEY` from The Odds API (https://the-odds-api.com/). The adapter requests
passing yards, rushing yards, receiving yards and receptions for individually
matched events. Coverage depends on the provider and book. Credentials stay in
Actions environment variables, never public JSON or browser JavaScript. Without
that secret the site shows production projections, but no fabricated quotes or
ticket suggestions. Quotes expire after six hours; the daily schedule does not
provide continuous live odds.

Projection v1 uses up to ten current-season recorded stat appearances (minimum
four), and requires an appearance in one of the team's last two games. Missing
stat rows are not zeros. Yard projections multiply the appearance average by
opponent yards allowed / loaded league average (bounded 0.85–1.15); receptions
are not adjusted. This heuristic is not fitted or calibrated and ignores role
changes, verified participation, pace and opponent strength. The tab explicitly
labels these limits. Scenarios are historical final-margin groups, not a fitted
in-game script simulator.

Estimated hit rates count matchup-adjusted observations beating a current line;
integer-line pushes do not count as wins. The SGP research builder only considers
two different players on the same team, the same bookmaker, and at least six
shared historical games. It counts joint outcomes rather than multiplying
marginal probabilities. Selecting the strongest pair introduces selection bias;
this is displayed. Cross-team correlation, validated future probabilities and
actual combined SGP prices are not implemented. The sportsbook must confirm
player eligibility, allowed combinations and combined payout. No bets are placed.

Validation: `node tests/test_sniper.cjs`; Python syntax checks and browser preview.
