# Katoptron (Κάτοπτρον)

Katoptron is a **nationwide Flock Safety camera-map and route-surveillance education project**. Its primary product combines an evidence-backed map, an optional planned-driving-route simulator, and separately linked government records. The map NEVER invents camera coordinates: exact pins and approximate areas require distinct source verification. All simulated detections are hypothetical; the site never accesses private Flock plate reads or tracks actual vehicles. The legacy synthetic simulator remains available separately.

## Current project status

- **Primary public experience:** [Nationwide camera map and route simulator](https://ayeemecee0.github.io/Katoptron/) is the homepage. Search arbitrary US start and destination points, display real roads from a public routing demo, inspect any published evidence-backed camera pins or uncertainty areas, and optionally replay clearly distinguished synthetic potential sightings.
- **Map records database:** [Migration 018](./supabase/migrations/018_camera_map_locations.sql) creates the RLS-protected `flock_camera_locations` table. 108 government GIS points are now published across Peoria AZ (74), Monroe WA (18) and El Paso County CO (16). Unmapped areas still do not demonstrate an absence of surveillance.
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


## Owner-bound automatic government GIS verification

The county expansion adds a [government root binding](./supabase/migrations/023_owner_bound_gis_authority.sql), a [live authority verifier](./scripts/auto_link_gov_gis.py), and [daily GitHub Actions](./.github/workflows/auto_link_gov_gis.yml). Owner-reviewed GIS authority is limited to a particular El Paso County government-operated host and exact Sheriff layer path. The verifier independently re-fetches the county government GIS web page, GIS map-service metadata, Flock_Cameras point layer schema, and nonempty bounded feature inventory. Only if all checks succeed does an auditable database function promote the source. Daily location ingestion then separately verifies current official layer metadata before public publication. Third-party ArcGIS layers still cannot be promoted solely from names or vendor mentions.

The first production run automatically approved the county's source and discovered 16 county Flock-camera points, raising the verified map inventory to 34. This is not a nationwide camera census, proof the devices are active, or evidence of real ALPR detections. To add a different government domain, its original government identity must first be independently established and root-scoped. The current verifier does not crawl every municipality or automatically trust arbitrary government subdomains.


## Production readiness

See [Current production readiness audit](./docs/production-readiness-audit-2026-10-22.md), [evidence methodology](./methodology.html), and [privacy](./privacy.html). Live source verification covers two jurisdictions only. Public demo route/geocoder infrastructure is not a production-scale service.


### Third verified GIS deployment: Peoria, Arizona

On October 22, 2026, Katoptron independently checked the City of Peoria government's GIS host, its Public Works MapServer point layer 286 explicitly named Flock Cameras, and its individual CameraID and Location fields. The live read-only probe returned 74 features with valid camera identifiers and geographic coordinates. Migration [026](./supabase/migrations/026_peoria_city_camera_source.sql) approved this exact municipality-operated layer; the existing daily verifier independently reread layer metadata, published 74 records, and rechecked 34 previously published points with zero production errors. These are published GIS points, not proof of active readings.


## Nationwide location/map milestones 1–3 (October 22, 2026)

**Government GIS discovery:** The older official-source pipelines remain, plus [daily nationwide 50-state search rotation](./scripts/discover_nationwide_gis.py) that accepts *only original public government webpages* into a private candidate queue. Because Bing and DuckDuckGo returned no usable .gov search hits in the first run, it now also seeds from the existing nationwide discovery/verified-agenda registry. The [independent GIS catalog scanner](./scripts/discover_government_gis_catalog.py) walks folders and layer metadata on owner-approved municipal GIS servers; a matching Flock layer becomes an unverified candidate, never automatically an approved host or a camera pin. Search/indexing may still miss government pages.

**Universal verifier:** [Profiles migration 028](./supabase/migrations/028_camera_profiles_history.sql) stores immutable owner-reviewed camera classification profiles, and [generic official GIS verifier](./scripts/auto_verify_camera_profiles.py) applies them without per-city Python exceptions. Its first production recheck qualified all 108 existing points and rechecked them without duplicate publications or withdrawals. New sources still require independent government authority and reviewed verification rules before automatic publication.

**Nationwide map usability:** The homepage adds city/address/map coordinates search, jurisdiction and record-label filters, explicit original source evidence tiers, and per-camera public [evidence event history](./supabase/migrations/028_camera_profiles_history.sql). A separate directory of [dated government programs without camera coordinates](./supabase/migrations/030_government_programs_without_coordinates.sql) includes original government publications from South Portland ME, Provo UT, League City TX, Perry GA and a **terminated** Los Altos Hills CA program. These are text/source records, **not fake pins or active-coverage assertions**. No credible deployment geometry source has yet qualified for publication of an approximate mapped area.

**Completion limitation:** The software stages and map interfaces are developed, but worldwide/nationwide evidence coverage remains sparse (108 government GIS points, three jurisdictions). Broad-source discovery, automatic government-root authenticity for newly discovered hosting providers, and independently verified approximate area geometries remain ongoing. Do not claim the entire nationwide camera inventory is complete.
