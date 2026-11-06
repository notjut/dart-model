
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

Sniper Sauce displays the provider’s sanitized error reason. `OUT_OF_USAGE_CREDITS`
means The Odds API account needs its quota renewed or replenished; changing a
stats-provider key does not resolve it. The per-game SGP control explains missing
quotes, expired quotes, lineup review, insufficient history, the 60% historical
leg screen, and pairing restrictions. Readiness is checked again on click.
No fallback lines, probabilities or prices are invented to force a ticket.

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

### Upset research phase one

The daily refresh collects regulation play-by-play into `upset-metric-history.json`.
A separate experimental forecast tests protection (offensive sacks allowed ×
opponent sack rate), run resistance (run share × opposing no-gain/loss rate),
and offensive touchdowns per drive. `scripts/upset_engine.py` fits a ridge
adjustment to earlier expanding-date core errors, with at least 60 training
rows and no same-day outcomes. Main forecasts and automated tickets do not use it.

Every game shows its source sample, test forecast and availability gaps. Official
reports are matched to both teams and date, with verified publication/retrieval
times. Reports do not identify starters. There are no injury, freshman, travel,
crowd or letdown point bonuses. Verified starting-QB changes and line continuity
remain an explicit data gap, rather than a fabricated adjustment. Sack rates are
a pressure proxy; TDs per drive are not red-zone conversion. Rates are not separately
opponent-adjusted; baseline team strength is retained.

Candidate/base pairs and their features are archived before kickoff.
`upset-research-results.json` grades only prospective snapshots actually recorded
before kickoff and includes losses, Brier score, margin error and outright
underdog selection records. Recovered snapshots and historical reconstructions
are excluded. Historical replay is development evidence only; no automatic
promotion or performance claim is permitted. Version changes must use a new
experiment ID. Moneyline ROI is not calculated.

Checks: `python -m unittest discover -s tests -p 'test_*.py'`,
`node tests/test_upset_research.cjs`, and the existing frontend checks.
### SportsDataIO supplemental injury checks

The existing daily refresh now runs `scripts/sportsdataio_check.py` immediately
after fetching official availability reports. Its Actions secret is
`SPORTSDATAIOAPIKEY` (the underscored alias `SPORTSDATAIO_API_KEY` also works).
Only the current InjuredPlayers and Teams endpoints are requested: two requests
per successful refresh, with one retry for a transient failure. No historical
or paid-plan upgrade is requested. Authentication stays in the request header;
redirects are refused and response bodies never enter logs.

This is a supplemental trial check. Team and player names must match exactly
after normalization; duplicate identities or incompatible positions are not
guessed. A report must be published, retrieved within 30 hours, published within
7 days, and match that game's date within the next 7 days. Unmatched names and
trial-only injury diagnoses/statuses are never published. Missing rows do not
mean healthy. Official statuses and verified center roles are never overwritten.

Matchup availability cards show matching statuses and disagreements in plain
language. The public `availability.json` and `refresh-status.json` contain the
same supplemental check run ID, check timestamp and aggregate counts (including
QB, center, OL and DL comparisons). Counts are player-report comparisons, not
unique players or an accuracy score. Provider failures remain visible without
discarding fresh official reports. The next refresh retries normally.

No injury point penalties, confirmed starters, historical injury histories or
new confidence percentages are inferred. Existing official QB concerns continue
to flag games for review and exclude them from automated tickets. Trial numeric
stats/odds are not used. Production redistribution rights and historical coverage
must be confirmed with SportsDataIO before broadening this use.

Validation: `python -m unittest discover -s tests -p 'test_*.py'` and
`node tests/freshness.cjs`.

### Matchup rankings

The existing daily refresh runs `scripts/team_rankings.py` to publish `team-rankings.json`. It retrieves ESPN’s published `fpirank` for each FBS team and the separate current-season `cfp` poll. It never substitutes AP or Coaches rankings. Team IDs, season, unique ranks, complete coverage and publication dates are checked. These rankings are display context; no forecast weights or historical picks are changed.

FPI and CFP badges appear beside teams on the board, matchup reports, Picks & Parlays, Seabiscuit cards, Sniper Sauce, history and result cards. The shared legend links to ESPN and shows both publication dates. Historical results explicitly label these as **current** rankings, not game-day rankings. CFP badges appear only for the Top 25 when a complete poll is available. Failed refreshes retain the last checked snapshot marked “older,” with its original timestamp, or show unavailable. A browser snapshot checked more than 30 hours ago is also labeled older. Publication-age limits are seven days for FPI and fourteen days for the weekly CFP poll.

The Pages verification checks the ranking run ID and coverage against the published refresh status. Tests run through the existing Python discovery and `node tests/freshness.cjs`.

## Opponent-adjusted main forecasts (v1)

`scripts/opponent_strength.py` fits separate offensive and defensive ratings for scoring, yardage, successful plays and explosive plays from completed, earlier-date FBS games in the current season. Venue is a separate term; each team effect has three game-equivalents of ridge shrinkage. Missing stat categories are excluded, never filled with zero. FCS games remain in records and Elo, but are excluded from adjusted performance inputs because their schedules are incomplete. Non-FBS forecasts retain the legacy fit and explicitly report missing adjustment coverage.

The main model replaces its raw production features with those estimates; it does not add a schedule bonus to the old inputs. The scoring window consequently changes from 12 rolling games to current-season FBS games. A paired expanding-date development replay compares the old and new methods on identical games in `model.json` → `opponentAdjustmentEvaluation`. This reconstruction is not proof of future accuracy. Existing saved picks and the frozen legacy benchmark are retained unchanged. Forecasts and snapshots carry model versions. The protection/run-resistance/TD-drive experiment uses a new version so comparisons do not silently mix baseline models.

### Started games stay visible

The Conference hub retains games from the last fourteen days in a Started & finished section, using the same week, conference and team filters. `started-games.json` is produced by the existing refresh from saved forecast archives. It shows the latest eligible pregame pick and pregame lines; no post-kickoff forecast or line can replace them. Missing archives are explicit. These cards never enter upcoming parlay or Seabiscuit selection. Scores appear only after completion; in-progress status is a dated snapshot with a box-score link. The public verifier checks its release ID.
