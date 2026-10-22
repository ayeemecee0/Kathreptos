# Katoptron production-readiness audit — October 22, 2026

## Scope

Nationwide source-backed Flock camera map, user-planned real-road synthetic surveillance simulator, accurate uncertainty labeling, public accountability records, automated government/OSM/community evidence discovery. Never pretend to access actual ALPR reads.

## Milestone order and state

| Priority | Milestone | State | Acceptance criteria |
|---|---|---|---|
| P0 | Database privileges and public source provenance | FIXED in migration 025 | Anonymous roles cannot call owner-bound source promotion or trigger internals; 34 records remain accessible via anon SELECT |
| P0 | Whole-route simulation accuracy | IMPLEMENTED and tests passing | Full route corridor queried, proximity measured against segments, timeline by distance traveled, unknown data not counted as zero |
| P0 | Original evidence lifecycle and source revocations | OPERATIONAL FOR TWO SOURCES | Government GIS points immutable, daily source checks, revocation withdraws |
| P1 | Municipality disclosure link crawler | IMPLEMENTED, LOW COVERAGE | Crawl approved official Flock-linked pages, stage direct ArcGIS URLs privately; first run checked 4 pages and found no new direct layer links |
| P1 | Expand verified GIS authority nationwide | PARTIAL | Only two currently approved municipal sources; third-party ArcGIS and OSM are private candidates |
| P1 | Real browser smoke testing and monitoring | INCOMPLETE | Test live public API, map and route; failures must produce alerts |
| P1 | Replace Photon and OSRM demo infrastructure | BLOCKED | Provision routing/geocoding services with suitable uptime/rate/privacy guarantees and configure provider credentials |
| P1 | Abuse-controlled community submissions | NOT STARTED | Protected intake, throttling, photo/source verification, consent and privacy restrictions |
| P1 | Accessibility and usability | PARTIAL | Mobile and keyboard walkthrough, screen reader audit, feedback and performance tests |
| P2 | Accountability directory for public officials and Flock leadership/employment | PARTIAL | Dated source links per claim, distinguish public decisions from employment; avoid personal addresses and inference |
| P2 | Nationwide camera completeness/history | PARTIAL | Repeatable geographic coverage metrics, expanded authority roots and change history |
| P2 | Operational launch controls | INCOMPLETE | Deployment smoke tests, backups, incidents, performance, legal/privacy review |

## Verified state

34 verified public points (18 Monroe WA, 16 El Paso County CO), two official approved GIS roots, 1,586 private OSM candidates and one third-party GIS candidate. Zero verified approximate areas. The original simulator and government records remain available.

The security audit uncovered a source-promotion RPC that was callable by anon/authenticated. Migration 025 explicitly revoked those grants and confirmed service-role-only execution. Supabase security advisors now flag only intended read-only helper predicates plus editorial authenticated functions requiring separate in-function reviewer authorization, and Auth leaked-password protection configuration.

Four original government disclosure pages checked in first crawler run yielded zero new exact GIS-layer links. Discovery infrastructure is not proof of nationwide verified coverage.

## Critical launch blockers

Reliable geocoding and routing infrastructure (current endpoints are public demos), broad verified geographic coverage, community intake moderation/abuse controls, real end-to-end browser testing, accessible mobile flows, incident response, Auth security settings and operational monitoring.

**Do not label the full project production-ready until these acceptance gates are satisfied.**
