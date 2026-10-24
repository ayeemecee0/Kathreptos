# Milestone 7 — Public evidence analytics
Implemented October 23, 2026.

## Purpose
Quantify what Katoptron has independently published, **not** how much surveillance exists nationwide. No visits, routes, plate histories, address searches, or user demographics are collected by this dashboard.

## Live public dashboard
[Evidence analytics](../analytics.html) reads three RLS-invoker public views in migration `074_readonly_public_analytics.sql`.

- `flock_analytics_overview`: independently source-verified exact GIS points; separately corroborated points; dated government program records (including historical terminations); published government accountability facts; sourced personnel roles; states with evidence. Categories are intentionally separate and **must never be summed as unique cameras**.
- `flock_analytics_states`: records original source-dated program inventory and verified georeferenced exact point counts by state. A state with no exact pins may still have documented Flock activity. States with no documented records are unknown, not camera-free.
- `flock_analytics_monthly_evidence`: month histogram of already published **record dates**. Undated records are excluded; documentary evidence volume is not a camera installation trend.

The dashboard offers state ordering, source category filtering, program dates, and a CSV export protected against spreadsheet formula injection. No unreviewed community reports, private data, or hypothetical observations appear.

## Production test snapshot
On October 23, production anonymous read-only queries returned 275 verified exact government GIS points, zero separately corroborated points, 20 source-dated programs, five program terminations at historical source date, 30 deduplicated accountability records, six states with exact GIS points and fourteen states with any documented evidence. These are point-in-time results subject to future source validation.

`scripts/test_analytics_m7.sql` tests analytics source reconciliation, caller-RLS view settings, nonnegative values and private-community isolation. The production database test passed.

## Release checks
`scripts/smoke_analytics.cjs` verifies the live dashboard in Chromium when browser smoke runs. Release verification completed: [Pages #649](https://github.com/ayeemecee0/Katoptron/actions/runs/40063927898), [validation #407](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928191), and [browser smoke #91](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928164) all passed. These checks validate public analytics rendering and counts, not nationwide completeness of Flock data.
