# Katoptron verification bottleneck: original GIS authority, October 24, 2026

## Verified point baseline

**293 canonical original-government GIS point records across seven jurisdictions.** The Alachua County, Florida alternate government-publisher pathway contributed 18 of these. No pending external Esri organization or private GIS candidate has been promoted merely because its ArcGIS layer is named "Flock Cameras". Counts denote source-documented locations, not confirmed active ALPR reads.

## Live triage result

[Private GIS verification triage #1](https://github.com/ayeemecee0/Katoptron/actions/runs/40132048463) completed successfully with all regression tests green. Its live backlog totals:

| Research candidates | Count | Safe next action |
|---|---:|---|
| Unverified GIS entries that are already trusted source URLs | 3 | Suppress redundant verification work; source trust remains in the canonical verified inventory |
| Additional government-hosted GIS source layers with every point within ~100 metres of existing source-backed locations | 2 | Hold as *possible* duplicates, do not publish duplicate pins; recheck if independently sourced original points diverge later |
| Externally hosted ArcGIS camera layers with no independent original-government endorsement | 7 | Verify the original publisher organization independently; require government evidence binding to that ArcGIS organization or exact layer |
| Newly verifiable distinct camera layers found in this triage | 0 | Do not manufacture new pins |

The two government-hosted overlaps contain **32 original GIS point features**, all with possible proximity matches in the existing published camera inventory. This is not independent proof that each is the same physical device, only a conservative reason to withhold duplicate publication until reviewed.

## Improved external hosted publisher lookup

[ArcGIS original-publisher audit #6](https://github.com/ayeemecee0/Katoptron/actions/runs/40132374011) passed:

- All 7 private external ArcGIS candidates had consistent **original Flock point-layer metadata** (not independent government camera authority).
- 6 of 7 resolved to an exact ArcGIS Feature Service publisher organization using the original item and/or public owner profile, with cross-checked item URLs and owner identity.
- 1 of 7 remains without a recoverable exact ArcGIS organization ID.
- **0 of 7 has a verified independent original-government endorsement.** Self-reported ArcGIS organization names and project titles cannot establish that a municipality, county or law enforcement agency owns, endorses or operates the camera layer.
- No photo data, unverified coordinates, unpublished private candidate URLs, or authentication secrets are printed in the public workflow logs.

## New ongoing automation

- [Candidate verification triage](../.github/workflows/triage_gis_verification_backlog.yml): twice weekly and upon code changes, inspect only previously authorized original-government GIS hosts for possible point overlaps. It groups external layers by the missing evidence requirements and prints hashed research IDs only.
- [Original ArcGIS publisher attribution](../.github/workflows/audit_external_arcgis_candidates.yml): weekly and on code changes, independently inspect exact Esri items and owner/org profile metadata. An organization claim is an investigation lead, never a government verification receipt.
- Existing registration, original-source refreshing, expiration and RLS checks remain the *only* systems allowed to publish or withdraw government-verified camera records.

## Next P0 priorities

1. **Government-to-Esri organization endorsement:** research original agency webpages containing direct links to a qualifying ArcGIS organization portal (not necessarily to an exact camera layer). Validate original domain and URL, unique authoritative item, original geometry, municipal jurisdiction, source status and independent corroboration before promoting an existing private candidate. Do not auto-promote an Esri account solely for calling itself a city.
2. **Original agency data expansion:** use the owner-reviewed first-party GIS registry rather than one off SQL procedure per city. Seed additional authority roots only from original agency GIS homepage and same-owned-domain provenance, not raw map-directory labels.
3. **Trust-preserving source deduplication:** keep nearby existing-government matches as possible duplicates while preserving provenance and monitoring for genuinely new points. Avoid counting the same location twice.
4. **Evidence stability checks:** on any vanished original webpage, modified original schema or incomplete feature-ID inventory, hold updates, preserve the provenance history, and recheck across time instead of immediately deleting a camera record.
5. **Infrastructure:** retain the no-paid-service policy and approximately 10% automated discovery maintenance budget.

**Acceptance limit:** The bottleneck is now classified and actively monitored, not completely resolved nationwide. More original government ownership disclosures are required before any of the seven externally hosted GIS candidates can become source-verified camera locations.
