# Katoptron (Κάτοπτρον)

Katoptron is a **nationwide Flock Safety camera-map and route-surveillance education project**. Its primary product combines an evidence-backed map, an optional planned-driving-route simulator, and separately linked government records. The map NEVER invents camera coordinates: exact pins and approximate areas require distinct source verification. All simulated detections are hypothetical; the site never accesses private Flock plate reads or tracks actual vehicles. The legacy synthetic simulator remains available separately.

## Current project status

- **Primary public experience:** [Nationwide camera map and route simulator](https://ayeemecee0.github.io/Katoptron/) is the homepage. Search arbitrary US start and destination points, display real roads from a public routing demo, inspect any published evidence-backed camera pins or uncertainty areas, and optionally replay clearly distinguished synthetic potential sightings.
- **Map records database:** [Migration 018](./supabase/migrations/018_camera_map_locations.sql) creates the RLS-protected `flock_camera_locations` table. At least 18 source-verified Monroe, Washington GIS camera points have been auto-published. Unmapped areas still do not demonstrate an absence of surveillance.
- **Archived fictional simulator:** [Original synthetic model](https://ayeemecee0.github.io/Katoptron/legacy-simulator.html) remains accessible for demonstrations.
- **Source-verified public database:** [Verified government records](https://ayeemecee0.github.io/Katoptron/records.html), backed by Supabase read-only public views and row-level security.
- **Automatic public evidence verification:** [Daily discovery workflow](./.github/workflows/discover.yml) finds official government matters, then [automatic Flock mention verification](./.github/workflows/auto_verify_agenda.yml) re-fetches live Legistar records and publishes only exact, source-verified agenda mentions with explicit Flock Safety titles. No manual click required.
- **Automatic legislative-action verification:** [Legislative decision verifier](./.github/workflows/auto_verify_decisions.yml) independently checks dated official Legistar history events, exact adoption/failure wording, governing body and matching pass/fail flag. The [public records page](./records.html) displays only qualifying events as *recorded legislative decisions*, not signed contracts. No manual review required for qualifying events.
- **Optional exceptions review:** [`agenda_evidence_reviews`](./supabase/migrations/006_legistar_source_integrity_and_review.sql) holds ambiguous or incomplete records. The [review dashboard](https://ayeemecee0.github.io/Katoptron/review.html) is available for difficult contract, action, or deployment claims, not required for already-proven official agenda mentions.
- **Explicit government-domain authority:** [Government-domain approval policy](./docs/official-government-domains.md) limits custom domains and ambiguous Legistar tenant aliases to individually reviewed government evidence.
- **Automated code and database checks:** [Validation workflow](./.github/workflows/validate.yml).

**Automation policy:** Public government agenda mentions with exact, re-fetched official API titles naming **Flock Safety** are published automatically. They are labelled as *agenda mentions*, never approvals, signed contracts, vendor payments, or installed cameras. Automatically verified legislative action events now have a separate evidence tier; signed contracts, individual votes and deployments still require stronger source rules.

Read the [automation and source-integrity policy](./docs/automatic-official-verification.md) for the current operating model. The [October 2026 project audit](./docs/project-audit-2026-10-21.md) documents the earlier manual-first architecture and the original data-quality findings.

## Source integrity and publication policy

- **Discovery is not verification.** Search snippets and news reports remain private. A government agenda mention may be published automatically only after an exact live API matter match, explicit Flock Safety in the official title, and pre-verified tenant/jurisdiction identity.
- **Flock Safety is not synonymous with ALPR.** Vendor identification must be explicit in the linked primary government source.
- **An authorization is not an executed contract.** Distinguish proposed, failed, adopted, signed, deployed, superseded, and terminated statuses. Do not infer an individual's vote from an agency-level decision.
- **Original primary sources:** official government records are linked wherever available. The Legistar API's `MatterId` is not assumed to equal a public LegislationDetail page `ID`.
- **Publication is evidence-tiered.** Official Flock agenda mentions and corroborated legislative action-history events are verified automatically in separate read-only public tables. The workflow service-role still cannot write verified human-edited actions, executed contracts, deployments or personal voting records. The optional reviewer interface remains for unresolved claims.
- **Privacy:** no private number plates, individual movement histories, personal addresses, or inferred real camera routes. All simulator vehicles, cameras, and detections are fictional.

## Repository

| Path | Purpose |
| --- | --- |
| [`index.html`](./index.html) | Synthetic simulator and clearly identified illustrative research links |
| [`records.html`](./records.html) | Live, verified public records; not the unreviewed news/agenda queue |
| [`scripts/discover.py`](./scripts/discover.py) | Unverified news leads |
| [`scripts/discover_official.py`](./scripts/discover_official.py) | Government-page discovery; **review-only** |
| [`scripts/discover_source_registry.py`](./scripts/discover_source_registry.py) | Conservative government-source and Legistar portal discovery |
| [`scripts/verify_government_sources.py`](./scripts/verify_government_sources.py) | Checks official government links, jurisdiction identity, and Legistar API access |
| [`scripts/discover_government_records.py`](./scripts/discover_government_records.py) | Bounded historical Legistar scanner, queues exact official API MatterIds |
| [`scripts/auto_verify_flock_agenda.py`](./scripts/auto_verify_flock_agenda.py) | Automatically verifies exact official Flock Safety agenda mentions from live API titles |
| [`scripts/auto_verify_legislative_decisions.py`](./scripts/auto_verify_legislative_decisions.py) | Automatically verifies exact dated full-legislative-body outcomes with corroborating pass/fail fields |
| [`.github/workflows/auto_verify_agenda.yml`](./.github/workflows/auto_verify_agenda.yml) | Runs after successful government discovery and on relevant updates |
| [`.github/workflows/auto_verify_decisions.yml`](./.github/workflows/auto_verify_decisions.yml) | Automatically verifies recorded legislative action events after source verification |
| [`supabase/migrations/013_automatic_verified_flock_agenda_mentions.sql`](./supabase/migrations/013_automatic_verified_flock_agenda_mentions.sql) | Immutable verified agenda mentions, public read-only policy and exact-provenance guards |
| [`supabase/migrations/015_auto_legislative_decisions.sql`](./supabase/migrations/015_auto_legislative_decisions.sql) | Independently verified, immutable, dated legislative events with revocation cascade |
| [`docs/automated-legislative-decisions.md`](./docs/automated-legislative-decisions.md) | Exact evidence requirements, interpretation limits and live validation logs |
| [`supabase/migrations/`](./supabase/migrations/) | Database schema, reviewed government-domain authority, editorial staging, and publication guards |
| [`docs/project-audit-2026-10-21.md`](./docs/project-audit-2026-10-21.md) | Full audit, known limitations, and next-step priority |

## Operations

The database is already created and connected. Migrations **003 through 015** have been applied to the existing Supabase project; migrations 001 and 002 were the initial schema setup. All new migrations are tested in a disposable PostgreSQL database before production.

To launch a new discovery run, use [Discover public Flock records](https://github.com/ayeemecee0/Katoptron/actions/workflows/discover.yml) and select **Run workflow** on `main`. The workflow runs daily on a schedule.

Only the Supabase **publishable key** is permitted in browser code. Keep the database service-role key restricted to GitHub Actions secrets and trusted server-side operations.

## Next milestone

Build automated verification for **executed Flock Safety contracts** from signed government agreements or equally authoritative contract records. Legislative-decision verification is now implemented and will publish only when explicit governing-body action, action date and pass/fail evidence agree. No future verification tier should infer signed contracts or deployments from proposal titles.

## Route/map MVP limitations and next milestones

The core map and route simulator are implemented as a static GitHub Pages site backed by a new read-only Supabase public camera-location interface. The API is intentionally empty until independent verification of specific camera coordinates or municipal deployment areas. This is not an all-camera census, and a city having Flock-related agenda records does not prove where cameras are deployed.

The **next implementation priority** is automatic camera discovery, source verification, and duplicate suppression from official georeferenced inventories and independently corroborated public data, holding uncertain reports unpublished. Only then will map pins appear. Community submissions should be accepted into private candidate storage, not automatically into the public map.

The beta uses [Photon's public demo geocoder](https://github.com/komoot/photon) and the [OSRM demo router](https://github.com/Project-OSRM/osrm-backend). They can throttle, reject or become unavailable. Before widespread traffic, use properly provisioned geocoding and routing infrastructure. Queries go from the user's browser directly to these services; Katoptron does not persist route searches, license plate numbers or inferred personal home/work locations.

The proximity simulation's 120-metre radius is an illustrative **route-to-mapped-point** distance threshold, not a manufacturer-specified camera reading range. Approximate program areas never produce point-camera detection events. An optional fictional-sighting toggle adds completely synthetic samples only to the route demonstration and never to the confirmed camera inventory.


## Daily nationwide camera-source pipeline (October 2026)

Official camera coordinates and crowdsourced claims have **separate security tiers**. The official GIS workflow checks only authority bindings already approved in the database and specifically supported by code. Its first production scan qualified 18 Monroe, Washington Flock ALPR cameras from the city's own camera-systems point layer. Record locations are immutable, new coordinate evidence uses distinct fingerprints, and missing/changed records are revoked only after a complete official inventory check. A separate freshness timestamp records successful rechecks.

The nationwide community import streams an OSM-derived US camera dataset maintained by FlockHopper/DeFlock, © OpenStreetMap contributors, ODbL 1.0. On its first successful production run, it inspected 143,968 ALPR features, found 115,934 Flock-tagged candidate entries, and submitted 1,586 records from one 30-day rotating shard to the **private unverified** research queue. That queue is NOT a list of verified Flock cameras. OSM mirrors are not independent corroboration of OSM.

Current remaining work: broaden official municipal GIS source bindings with separate government evidence for each city; implement independent-source corroboration for queued community points; provide rate-limited community submission intake; and add administrative alerting for delisted GIS assets. No routine manual approval is required for fully proven source-bound GIS records, and uncertain cases stay private.


## GIS discovery expansion and evidence revocation (Oct 21, 2026)

New ArcGIS layers cannot be assumed to be government-owned merely because their titles say Flock. The [GIS candidate workflow](.github/workflows/discover_camera_gis_sources.yml) checks pinned ArcGIS point layers and queues metadata privately. Savannah municipal council Flock procurement records do not independently establish ownership or installation status of a specific ArcGIS layer, so those layers remain unverified candidates, never new public camera pins.

[Migration 021](supabase/migrations/021_camera_gis_authority_candidates.sql) ensures new government GIS camera publications require currently verified source/jurisdiction authority, and revoking authority withdraws already published pins from anonymous queries. The scheduled worker cannot approve new authoritative sources.

The [cross-source evidence matcher](.github/workflows/match_camera_evidence.yml) compares OpenStreetMap community reports with already verified municipal GIS camera positions using a maximum 30-meter proximity threshold. [Migration 022](supabase/migrations/022_camera_source_matches.sql) recalculates distance server-side and rejects mismatches. These private evidence links are not additional public cameras. Unmatched reports stay private.
