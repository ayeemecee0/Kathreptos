# Evidence publication tiers (October 23, 2026)

## Principle

Katoptron preserves one strict, historically sourced government camera inventory and accepts **multiple independently validated ways to prove a location**. Candidate retention, provisional publication and authoritative government verification are distinct decisions. An ArcGIS title, OSM label, city procurement announcement, or single community submission never becomes a verified camera automatically.

## Database architecture

- Legacy canonical `flock_camera_locations`: existing source-bound government-verified records, their existing RLS, source-health checks and public statistics. **Unaffected**.
- `flock_point_evidence_cases`: separate research cases with `candidate`, `government_verified`, `independently_corroborated`, `rejected` or `withdrawn` classifications. Review metadata and case coordinates are not publicly visible unless live evidence requirements pass.
- `flock_point_evidence_attestations`: private reviewed evidence sources, stable upstream `source_family` identifiers, original URLs, proof digests, coordinates, review reasons and check timestamps. One source replicated by multiple map directories cannot be counted twice.
- `katoptron_internal.point_case_public`: a narrow SQL security-definer **read-only** eligibility predicate in a non-Data-API schema. It requires owner-reviewed cases and evidence, adequate geospatial agreement, check freshness, and no overlapping canonical point.
- `flock_public_tiered_camera_points`: `security_invoker` read-only public view. RLS only admits evidence-eligible cases. No public grants exist on attestation data or internal review explanations; service-role workflow has staging-only insert columns and cannot update verified statuses.

## Acceptable proof paths

### A. Government verified

An individually reviewed exact point from an agency-operated GIS source, an independently authenticated agency-owned ArcGIS organization, **or** an original government document containing actual georeferenced camera positions. Requires an original authority URL, provenance and reviewer rationale, and a successful evidence check within 365 days. This path is independent of a mandatory hyperlink from a precise government webpage to a single ArcGIS layer. Verified title alone never qualifies.

### B. Independently corroborated (provisional)

Two individually reviewed sources with different underlying `source_family` origins, whose original coordinates fall within about 50 m of the proposed point. At least one source must provide first-hand field documentation, independently originated reporting, or authenticated governmental material. Two OpenStreetMap copies, two rehosts of one GIS map, or a source without verified Flock vendor/device identity **do not** suffice. Each counted attestation must be rechecked within 180 days. Reviewer sign-off is mandatory until an independently proven automated source-validation mechanism can meet equivalent criteria.

### C. Candidate, withdrawn, rejected

Unverified and submitted evidence stays in private collection; no public pin or modeled exposure is inferred. A rejected case remains private. Live revocation or lapse of necessary source verification automatically hides the public case without erasing evidence history.

## Map and simulator contract

- Canonical verified camera points remain default teal/amber map pins; independently reviewed alternate-government cases also qualify as official points.
- Independently corroborated points use a **separate labeled optional map layer**, off by default. Source details identify provisional status; 0 visible candidates means evidence unknown, not no cameras.
- Default route simulator reads canonical and reviewed government evidence, never provisional point data or OSM-only reports. It does not claim actual reads, device uptime, camera direction or surveillance-free roads.
- The public canonical national statistics remain based on `flock_camera_locations` and are not inflated with provisional points or duplicate cases.

## Controls tested

PostgreSQL regression covers: no public candidate leaks; reviewed agency-owned ArcGIS authority path; same-upstream source mirrors do not corroborate; cross-family corroboration does; coordinate disagreement hides corroboration; 180-day review expiry hides corroboration; evidence withdrawal hides corroboration immediately; no service-role promotion privilege; no anonymous read of private attestations. The web browser smoke additionally reads the new public view and expects private attestations to be denied.

## Important implementation boundary

**This migration establishes a genuinely usable tiered schema, live eligibility logic and map representation; it does not automatically authenticate previously unverified external ArcGIS candidates or community reports.** The existing 7 external ArcGIS layers lack government association receipts and remain held. The 8,186 pre-existing private OSM community leads are retained, not turned into provisional map pins by their presence alone. New corroborated publications require evidence reviewed under the stricter source-independence standards, either via a future approved automated evidence reconciler or an authorized editorial workflow. Avoid suggesting that merely creating a publication table proves any new camera facts.

Next: feed genuinely independent firsthand/agency attestations through the existing private review interface and a tested source-authority automation; never give a discovery worker authority to mark an untrusted source `reviewed`.
