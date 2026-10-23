# Katoptron production-readiness audit — October 22, 2026

## Scope

Nationwide source-backed Flock camera map, user-planned real-road synthetic surveillance simulator, accurate uncertainty labeling, public accountability records, automated government/OSM/community evidence discovery. Never pretend to access actual ALPR reads.

## Milestone order and state

| Priority | Milestone | State | Acceptance criteria |
|---|---|---|---|
| P0 | Database privileges and public source provenance | FIXED in migration 025 | Anonymous roles cannot call owner-bound source promotion or trigger internals; 206 records remain accessible via anon SELECT |
| P0 | Whole-route simulation accuracy | IMPLEMENTED and tests passing | Full route corridor queried, proximity measured against segments, timeline by distance traveled, unknown data not counted as zero |
| P0 | Original evidence lifecycle and source revocations | OPERATIONAL FOR TWO SOURCES | Government GIS points immutable, daily source checks, revocation withdraws |
| P1 | Municipality disclosure link crawler | IMPLEMENTED, LOW COVERAGE | Crawl approved official Flock-linked pages, stage direct ArcGIS URLs privately; first run checked 4 pages and found no new direct layer links |
| P1 | Expand verified GIS authority nationwide | PARTIAL | Five currently approved municipal sources; third-party ArcGIS and OSM are private candidates |
| P1 | Real browser smoke testing and monitoring | INCOMPLETE | Test live public API, map and route; failures must produce alerts |
| P1 | Replace Photon and OSRM demo infrastructure | BLOCKED | Provision routing/geocoding services with suitable uptime/rate/privacy guarantees and configure provider credentials |
| P1 | Abuse-controlled community submissions | NOT STARTED | Protected intake, throttling, photo/source verification, consent and privacy restrictions |
| P1 | Accessibility and usability | PARTIAL | Mobile and keyboard walkthrough, screen reader audit, feedback and performance tests |
| P2 | Accountability directory for public officials and Flock leadership/employment | PARTIAL | Dated source links per claim, distinguish public decisions from employment; avoid personal addresses and inference |
| P2 | Nationwide camera completeness/history | PARTIAL | Repeatable geographic coverage metrics, expanded authority roots and change history |
| P2 | Operational launch controls | INCOMPLETE | Deployment smoke tests, backups, incidents, performance, legal/privacy review |

## Verified state

206 verified public points (74 Peoria AZ, 53 Webster TX, 45 Lawrenceville GA, 18 Monroe WA, 16 El Paso County CO), four government-authorized GIS host bindings plus the legacy Monroe municipal verifier, 1,586 previously identified private OSM candidates, and ten private GIS source candidates. Zero verified approximate areas. The original simulator and government records remain available.

The security audit uncovered a source-promotion RPC that was callable by anon/authenticated. Migration 025 explicitly revoked those grants and confirmed service-role-only execution. Supabase security advisors now flag only intended read-only helper predicates plus editorial authenticated functions requiring separate in-function reviewer authorization, and Auth leaked-password protection configuration.

Four original government disclosure pages checked in first crawler run yielded zero new exact GIS-layer links. Discovery infrastructure is not proof of nationwide verified coverage.

## Critical launch blockers

Reliable geocoding and routing infrastructure (current endpoints are public demos), broad verified geographic coverage, community intake moderation/abuse controls, real end-to-end browser testing, accessible mobile flows, incident response, Auth security settings and operational monitoring.

**Do not label the full project production-ready until these acceptance gates are satisfied.**


## Additional verified completions from October 22

- **Peoria AZ now live:** 74 newly sourced official GIS camera points added by automated verifier, bringing the production verified total to 108 across three jurisdictions. Corrected CI migration checks for the third verified government GIS root. All published exact locations have evidence links; no camera uptime or plate reads are implied.
- **End-to-end browser checks passing:** Headless Chromium release smoke tested the three municipalities against the actual public Supabase camera API, plus simulated road-route evidence, replay and reset. Job: https://github.com/ayeemecee0/Katoptron/actions/runs/39810600259. The workflow now also tests local checkout changes on push, avoiding races with GitHub Pages deployment.
- **Daily public-health monitor:** New script/workflow validates published site assets, source-check freshness (72-hour threshold), baseline minimum counts, and no revoked camera record leakage. First live run passed (https://github.com/ayeemecee0/Katoptron/actions/runs/39811207783). An intentional verified camera withdrawal below a baseline will fail the monitor until an evidence audit updates the baseline.
- **Database performance repair:** Migration 027 adds eight missing foreign-key indexes on government-record and editorial tables; Supabase performance advisor no longer reports any unindexed foreign keys. New unused-index advisories are informational immediately after creation.
- **Complete migration and code CI:** October 22 latest validation run https://github.com/ayeemecee0/Katoptron/actions/runs/39811440690 passed with migrations 001 through 027 and all discovered script tests.

The following remain **not production-ready**: authenticated anti-abuse community reporting with evidence validation, independent GIS authority discovery at broad national scale, dedicated geocoder/router infrastructure and provider privacy guarantees, accessibility/user research, sustained load testing, operational response and backups, Auth password-leak protection dashboard configuration, and the full sourced personnel/accountability directory. Do not claim an exhaustive nationwide camera inventory.


## Milestones 1–3 implementation details (October 22)

- Reusable owner-reviewed GIS camera classification profiles now live (migration 028), with automatic all-source production verification. It rechecked 108 original GIS points with zero withdrawals or failures. A separate public evidence history ledger records publication/recheck events, with RLS exposing histories only for currently verified points.
- Rotating 50-state original-government web discovery (migration 029, daily workflow) plus an owner-verified ArcGIS service-catalog scanner. The first web-only Bing/DuckDuckGo pass yielded zero original government hits and thus no verified new sources, prompting integration of existing national discovery-queue/verified government record URLs. The service catalog scanner is a new additional discovery path and may not discover a deployable camera source immediately.
- Map location search, map-only jurisdiction and text filtering, source-evidence history, and evidence-tier labels are implemented. They do not change planned-route evidence matching.
- A five-jurisdiction public **government program record directory without camera coordinates** is now implemented with dated original source links; Los Altos Hills is correctly labeled as terminated. Zero unsupported approximate camera regions have been fabricated.
- **Not yet achieved:** national verified point coverage, production-scale geocoder/routing providers, independent validation of newly found municipal GIS hosting roots at broad scale, documented uncertainty polygons, fully automated candidate corroboration into new approved profiles without unsafe authority promotion.


## October 22 additional production milestone

Verified 206 public original-government GIS camera points across five jurisdictions: Peoria AZ 74, Webster TX 53, Lawrenceville GA 45, Monroe WA 18, El Paso County CO 16. The October 22 production verification run explicitly excluded ten Lawrenceville school camera records in the city GIS source; all previously verified points were rechecked without withdrawals. Source approval under migration 031 is government-root reviewed and independent of the discovery-candidate registry. The daily health monitor and Chromium smoke now require the two new municipal datasets. Routine automated discovery remains an incomplete national-data acquisition process and cannot guarantee exhaustive nationwide source coverage.


## Continued work, October 22

- [Lawrenceville city government GIS](https://www.lawrencevillega.org/592/GISMaps) publicly links city-operated Flock map and portal. Live GIS layer lists 55 points, 45 expressly marked PD Flock Camera, 10 marked PD School Camera. **Only the 45 Flock records qualify** and are published.
- [Webster city Maps page](https://www.webstertx.gov/868/Maps) links the city's GIS host. Its original Flock PD license-plate-camera service has 53 identified bounded points. These have been published with original GIS evidence and source-check dates; they are not live ALPR readings.
- Migration 031 added two exact host/layer identities and independently reviewed data-driven verifier profiles, including Lawrenceville manufacturer-type filtering. The production pipeline published 98 and rechecked 108, with zero withdrawals or errors. Database revocation behavior was verified in a rollback-only transaction to keep records intact.
- Current public camera record total 206 across five jurisdictions. [Public monitor](https://github.com/ayeemecee0/Katoptron/actions/runs/39825282715) passed after baselines expanded to five regions. Latest complete migration/code CI passed.
- [Esri public catalog discovery](../scripts/discover_arcgis_catalog.py) now privately acquires Flock-labeled GIS candidate links. First run found 15 services, checked 14 and staged six new unverified layers; total private candidate source URLs 10. **No public points** were published based only on those candidate titles.
- Remaining milestone 1 gap: independently authenticate newly discovered official government domains and ArcGIS organizations at broad national scale, cross-correlate source claims, and safely instantiate source policies. Milestone 3's approximate areas still require actual documented location geometry. Nationwide camera completeness is not attainable solely through software.

## Continued verification and infrastructure repair

- Updated smoke-test runner to a pinned official Playwright image; [browser run 39826753143](https://github.com/ayeemecee0/Katoptron/actions/runs/39826753143) passed. Browser dependencies no longer require repeated installation of OS packages.
- Found that national government-source discovery was fetching 529 mixed news candidates in a single call beyond a 50 KB backend response limit. Paged, filtered original-government URLs now succeed without the truncation error.
- The first resumed [nationwide discovery run](https://github.com/ayeemecee0/Katoptron/actions/runs/39827804174) found 7 government URL seeds and checked 5 original pages, staging four Flock-related government research leads. None was promoted to a camera pin.
- Implemented [direct government GIS link corroboration](../scripts/corroborate_candidate_government_links.py) with original page fingerprint, exact hyperlink, independent government page seed and private-only receipts. [Production run 39827803910](https://github.com/ayeemecee0/Katoptron/actions/runs/39827803910) checked 10 accessible pages against 10 GIS candidates and found zero qualifying exact layer backlinks. No approvals or camera publications were fabricated.
- The government-program citation table initially lacked backend SELECT permission despite being publicly readable; [migration 032](../supabase/migrations/032_readonly_backend_government_program_citations.sql) grants service-role SELECT **without** INSERT/UPDATE/DELETE and preserves anonymous denial of private GIS evidence receipts. Verified by live SQL.
- **Inventory remains 206 independently GIS-sourced Flock camera records across five jurisdictions.** New research findings and source discovery infrastructure do not represent more verified cameras. Five-region health monitoring remains enabled.
- **Still not completed:** trustworthy automatic government-ownership attestation for new ArcGIS hosting organizations and exact individual camera coordinates nationwide, source-backed approximate area polygons, robust routes/geocoding service SLA, accessibility/load testing and community intake protections. These continue to block describing the product as production-ready or the map as an exhaustive national ALPR census.

## Latest milestone 1–3 technical implementation and evidence gap

Implemented an automatic first-time government-owned GIS source approval mechanism (migration 039), requiring a current original .gov Flock-specific webpage linking the exact same-government-apex Flock GIS layer, complete camera records, bounded coordinates, no duplicates and database-side verification. Added append-only government-page digest rechecks (migration 042) so routine HTML changes do not permanently block legitimate links. Distinct external ArcGIS government endorsements require an already reviewed original municipal source, a fresh exact hyperlink, separate original ArcGIS organization identity proof and the same complete feature checks (migrations 036–038). Source-specific withdrawal is supported for both classes; failed websites do not count as proof that deployment ended. Generic source-profile verification continues to support all existing government hosts.

Map source-linked polygon support (migration 035) is deployed. Only original-government area geometry is eligible; no qualifying Flock polygon was available at the last production check. The public inventory still contains 206 camera points across five jurisdictions. The private GIS candidate pool contains 10 source layers and four original-government research webpages, none independently qualified for automatic publication as an additional camera source. The automated software is in place; **comprehensive nationwide evidence and approximate areas are not available from these source records**.

All newly implemented trust/camera RPCs deny anonymous execution; independently reviewed source keys and original-document evidence remain prerequisites. Latest full GitHub validation and deployment for commit 6ea4278a passed. Supabase's performance advisor no longer reports unindexed foreign keys. Existing authenticated editorial SECURITY DEFINER function and Supabase Auth dashboard warnings remain outside the current milestone and must receive security review before a full production launch.


## October 23 continuation: reliability and external-ArcGIS government endorsement

- Production GIS verifier had reported a transient Webster service timeout and an occasional empty Monroe response. The generic verifier now retries only network/empty/truncated failures with bounded backoff. It continues to **hold** existing published locations rather than retracting them on transient source outages; permanent metadata violations still fail closed. Latest read-only profile test found all five GIS sources, 206 eligible Flock points and ten excluded Lawrenceville school cameras.
- Migration [036](../supabase/migrations/036_government_direct_arcgis_service_link_receipts.sql) distinguishes original-government links directly to an ArcGIS numbered layer from hyperlinks to the parent ArcGIS service. The [link worker](../scripts/corroborate_candidate_government_links.py) maps a service-root link only when exactly **one** private Flock-specific layer belongs to that service, records a private provenance receipt, and never automatically grants third-party hosting authority.
- There are currently eleven private candidate GIS layers. No qualifying external government backlink established source authority in the latest checks; published camera count stays 206. A public ArcGIS title, uploader name, or anonymous point layer is insufficient for an authenticated camera claim.
- **Remaining milestone 1–3 evidence dependency:** Independent original-government attestations for third-party ArcGIS organizations and original source-backed approximate-area polygon geometries are not available for many jurisdictions. Additional source approval must wait for such evidence; no fabricated locations or municipal radius assumptions should be published.


## October 23 additional implementation and validation

- Reviewed five newly found original-government disclosures and deployed migration 047 as **dated, source-linked program records**, bringing the public government program directory to 10. Official Leander, Texas documentation explicitly says its Flock use ended September 4, 2026; Shakopee, Minnesota documentation identifies seven ALPR camera sites, some offline or relocating. There are no inferred GIS points or fictional polygons for these program records.
- Hardened the external ArcGIS city-government service-root approval path: the original ArcGIS service must list **exactly one Flock camera layer**, not merely one Flock-labeled candidate returned by a partial discovery index. Added positive/negative regressions for extra Flock layers, wrong IDs, absent layers, and direct-layer provenance.
- Updated the production health minimum to 10 independently reviewed government program records and broadened browser smoke to validate terminated Leander and the Shakopee offline caveat. Camera GIS baseline remains 206 across five jurisdictions.
- National verified camera coverage remains explicitly incomplete: approved exact geometries are published, unverified GIS layers are held, original-government statement-only programs are listed separately, and no unverified 2D deployment boundary is drawn.


## October 23: source-separated nationwide footprint

- Added migration 048 and a security-invoker public state evidence index that combines the **counts** of published exact GIS pins with separately dated municipal Flock program reports. The index does not combine their geometries or claim that a program implies operational cameras.
- Current public evidence spans nine states by at least one category: five with verified GIS points (AZ, CO, GA, TX, WA), and four currently represented only by dated government program records (CA, ME, MN, UT). Two government source records are expressly terminated; no camera locations are inferred from those statements.
- Updated map state browse UI to distinguish zero published coordinates from a verified absence of cameras, display termination counts, and explicitly label unmapped program-only states. CI and release browser tests check this distinction.
