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

## Current blockers for calling Milestone 4 production-grade
- Public OSRM/Photon demos have no contracted uptime or guaranteed rate limits; paid/self-hosted endpoints must be provisioned and tested under production load. This code does **not** secretly set up paid routing, data retention or credentials.
- Nationwide camera evidence is incomplete, so a fully checked route only means comparison to Katoptron's published evidence inventory, not detection absence.
- More accessibility, mobile, error-state, performance and contracted-provider smoke tests are required.

## Next actionable technical tasks
1. Provision privacy-reviewed dedicated/geocoding routing infrastructure and switch `config.js` to stable compatible endpoints. Do not embed API secrets in public code.
2. Add route alternatives side-by-side summary of *documented proximity* and *unknown geographic coverage* once every alternative has independently passed evidence querying.
3. Add user-controlled geocoding candidate disambiguation to prevent routing to the wrong city/state when text labels collide.
4. Continue original-government GIS backlink discovery in the scheduled jobs; do not promote ArcGIS organization names or program announcements as verified exact cameras.
