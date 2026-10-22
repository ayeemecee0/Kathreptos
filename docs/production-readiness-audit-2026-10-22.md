# Katoptron production-readiness audit — October 22, 2026

## Scope

Nationwide source-backed Flock camera map, user-planned real-road synthetic surveillance simulator, accurate uncertainty labeling, public accountability records, automated government/OSM/community evidence discovery. Never pretend to access actual ALPR reads.

## Milestone order and state

| Priority | Milestone | State | Acceptance criteria |
|---|---|---|---|
| P0 | Database privileges and public source provenance | FIXED in migration 025 | Anonymous roles cannot call owner-bound source promotion or trigger internals; 108 records remain accessible via anon SELECT |
| P0 | Whole-route simulation accuracy | IMPLEMENTED and tests passing | Full route corridor queried, proximity measured against segments, timeline by distance traveled, unknown data not counted as zero |
| P0 | Original evidence lifecycle and source revocations | OPERATIONAL FOR TWO SOURCES | Government GIS points immutable, daily source checks, revocation withdraws |
| P1 | Municipality disclosure link crawler | IMPLEMENTED, LOW COVERAGE | Crawl approved official Flock-linked pages, stage direct ArcGIS URLs privately; first run checked 4 pages and found no new direct layer links |
| P1 | Expand verified GIS authority nationwide | PARTIAL | Three currently approved municipal sources; third-party ArcGIS and OSM are private candidates |
| P1 | Real browser smoke testing and monitoring | INCOMPLETE | Test live public API, map and route; failures must produce alerts |
| P1 | Replace Photon and OSRM demo infrastructure | BLOCKED | Provision routing/geocoding services with suitable uptime/rate/privacy guarantees and configure provider credentials |
| P1 | Abuse-controlled community submissions | NOT STARTED | Protected intake, throttling, photo/source verification, consent and privacy restrictions |
| P1 | Accessibility and usability | PARTIAL | Mobile and keyboard walkthrough, screen reader audit, feedback and performance tests |
| P2 | Accountability directory for public officials and Flock leadership/employment | PARTIAL | Dated source links per claim, distinguish public decisions from employment; avoid personal addresses and inference |
| P2 | Nationwide camera completeness/history | PARTIAL | Repeatable geographic coverage metrics, expanded authority roots and change history |
| P2 | Operational launch controls | INCOMPLETE | Deployment smoke tests, backups, incidents, performance, legal/privacy review |

## Verified state

108 verified public points (74 Peoria AZ, 18 Monroe WA, 16 El Paso County CO), three government-authorized GIS source bindings, 1,586 private OSM candidates and one third-party GIS candidate. Zero verified approximate areas. The original simulator and government records remain available.

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
