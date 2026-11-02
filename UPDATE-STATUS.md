# The Darkhorse Model — daily updater

Repository: https://github.com/notjut/dart-model
Public site: https://notjut.github.io/dart-model/
Base commit: 23b2cdf43aaa447dd2a5b44249f16fd6b0735b16

This release adds automatic daily refresh and publishing plus interactive matchup charts.
Production run and deployment status are recorded in GitHub Actions and refresh-status.json.

## What the update does

- Runs the public data collectors, rebuilds future forecasts and preserves saved forecasts.
- Checks all 138 team schedules and required game summaries before replacing current data.
- Retrieves public availability, QB usage, line-related reports, travel, weather and matchup history.
- Grades saved winner, spread and total picks using pregame forecast and quote timestamps.
- Keeps experimental models and reconstructed historical evaluation separate from issued picks.
- Shows a stale-data banner after 30 hours and excludes stale model inputs from tickets.
- Uses rolling weeks instead of fixed October dates.
- Packages and publishes GitHub Pages only after checks pass; verifies the public release ID afterward.

## Finishing the deployment

1. Use authorized GitHub write access for notjut/dart-model.
2. Check the remote for changes before applying this update; do not force-push.
3. Verify Pages uses GitHub Actions and that the workflow can write repository content and deploy Pages.
4. Push the checked changes to main. The workflow also supports manual dispatch.
5. Watch the refresh and deployment finish, then verify the public refresh-status.json and model.json share the new run ID.
6. Confirm the enabled daily schedule. The workflow is configured for 13:17 UTC: 8:17 a.m. EST / 9:17 a.m. EDT. GitHub may queue scheduled runs.

The updater can run with `python scripts/daily_refresh.py` after installing requirements.txt.
It stages data in .refresh-work and keeps caches out of Git. An exception blocks publication.

## Remaining model limitations

Injury and QB reports are refreshed context, not fitted numerical score adjustments.
Only reported QB availability concerns can be used to suppress automatic tickets; missing reports do not imply a healthy roster.
An unattended refresh does not guarantee more accurate predictions or more complete provider coverage.
Historical player-availability data and broader validation are still needed before promoting those numerical effects.

## Checks

Python tests cover outright upset versus cover, pushes, no-picks, postgame leakage,
latest-pregame selection, incomplete-source rejection and started-game rejection.
Node checks cover stale inputs and week rollover. Browser QA checks the stale banner,
ticket suppression, current-week slate and saved-result presentation.
