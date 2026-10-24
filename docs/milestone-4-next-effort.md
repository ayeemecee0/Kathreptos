# Katoptron — Milestone 4 route simulation increment

## Product focus
Milestone 4 (reliable nationwide planned-route surveillance simulation) is prioritized over further manual GIS expansion. Automated GIS discovery and read-only external-source metadata checks continue, with original-government links required before any camera publication. Approximate polygons remain supplementary source evidence, never a blocker for route development.

## Implemented in this increment
- OSRM `alternatives=true` routes (up to three distinct returned routes) are parsed by standalone `routing-routes.js`, with explicit US coordinate, geometry, duration, distance and route-endpoint validation.
- The public simulator provides an accessible alternative selector with distance/time estimates. Each selected route queries the **whole corridor** independently. Evidence fetches aborted by route switching/reset cannot overwrite current observations.
- Evidence lookup remains read-only and never treats a failed or incomplete query as zero cameras. Actual plate reads, detections, uptime and license-plate lookups remain unavailable.
- External routing and geocoding fetches are HTTPS-only, no-store, timeout-limited and bounded by response size. The public `config.js` allows deploying compatible self-hosted/managed Photon and OSRM endpoints **without** placing credentials in client JavaScript.
- Test suite includes standalone route-alternative validation, static map requirements, and a Chromium smoke scenario switching between two deliberately different mock OSRM routes and checking fresh evidence.

## Discovery / candidate verification (secondary effort)
- Seven privately staged `services*.arcgis.com` Flock-labeled candidates had individually valid live point-layer metadata in the first read-only audit. **None** had an independent exact original-government hyperlink receipt, so **none** is approved as a government-owned camera source.
- New weekly `audit_external_arcgis_candidates.yml` checks live layer IDs, names, point geometry and object-ID metadata; flags withdrawn/changed layers and potential duplicate trusted sources. It cannot promote or publish cameras. Subsequent workflow logs emit opaque hashes, not private unapproved URLs.
- For one hosted service, the ArcGIS public service catalog includes Shelbyville-labeled municipal layers, and Shelbyville TN municipal records document a Flock program. This is a research lead **only**, not sufficient proof that a specific camera point layer is government-endorsed. The existing attestation worker still requires exact government linking plus organization and feature integrity.

## Subsequent Milestone 4 increment: route-by-route evidence comparison

- Every returned driving alternative is now independently checked across its *entire* camera-evidence corridor (bounded API workers and independent error isolation). Full route results are cached for selection, so choosing another route does not silently reuse the first route's evidence.
- The UI provides selectable side-by-side cards with driving distance, estimated duration, source-backed exact camera points within a clearly hypothetical 120-meter *road-proximity band*, separately identified approximate areas, and stale/unknown source-check timestamps.
- Evidence status is per route: pending / complete / unknown. A truncated or malformed source response, failed PostgREST call, or unsupportable corridor yields **Unknown**, never "zero cameras" or a surveillance-free claim.
- Travel routes are **not ranked by risk or likelihood of detection**. Existing verified points cannot establish camera uptime, recognition angle, read range, or an actual plate read.
- US geocoder lookups now require the user to choose their intended location if Photon reports multiple distinct candidate places. A changed address invalidates the earlier selection. Entering literal US lat/lon avoids ambiguous geocoder selection.
- Dedicated routing and geocoding production service availability is still unprovisioned. A configured HTTPS provider with a reviewed privacy/availability commitment remains a required external launch dependency, not something automatically solved by front-end code.
- Regressions cover comparison proximity/deduplication, provisional-source exclusion, stale/unknown timestamps, accessible comparison cards, switching/clearing independent source results, and ambiguous US cities.

## Current blockers for calling Milestone 4 production-grade
- Public OSRM/Photon demos have no contracted uptime or guaranteed rate limits; paid/self-hosted endpoints must be provisioned and tested under production load. This code does **not** secretly set up paid routing, data retention or credentials.
- Nationwide camera evidence is incomplete, so a fully checked route only means comparison to Katoptron's published evidence inventory, not detection absence.
- More accessibility, mobile, error-state, performance and contracted-provider smoke tests are required.

## Next actionable technical tasks
1. Provision privacy-reviewed dedicated/geocoding routing infrastructure and switch `config.js` to stable compatible endpoints. Do not embed API secrets in public code.
2. Monitor the independently checked route comparison in production, enforce API error budgets, and add provider contract/health monitoring. Distinguish a successfully checked *published inventory* from unknown actual camera coverage.
3. Expand end-to-end tests for ambiguous Photon names, provider outages, and long corridors before general launch.
4. Continue original-government GIS backlink discovery in the scheduled jobs; do not promote ArcGIS organization names or program announcements as verified exact cameras.

## October 24 route-integrity acceptance (free-provider deployment)

The actual configured browser provider is **Geoapify**, with the OSRM/Photon demos retained as an explicit alternate configuration only. The older description above that a live production provider is *unprovisioned* is out of date: free-tier Geoapify requests and the authorized production origin have been exercised by the live Chromium route smoke. However, **daily quotas, account-side origin restrictions, API longevity and an uptime commitment are not independently signed off.** These remain genuine capacity/credential safeguards.

Geoapify MultiLineString conversion now rejects disconnected road segments rather than inventing a straight-line connector that could produce a false simulated route. Harmless sub-centimeter boundary rounding is tolerated; a multi-meter discontinuity fails shut. [Validation #447](https://github.com/ayeemecee0/Katoptron/actions/runs/40108532736) passed its geometry regression and [Browser smoke #114](https://github.com/ayeemecee0/Katoptron/actions/runs/40108637053) passed complete route flows after deployment.

A second route request clears old camera proximity counts and replay immediately; if the provider fails, the new trip has **unknown** evidence rather than displaying old-trip results.
