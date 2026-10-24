# Government GIS verification without an exact camera-layer backlink

**Status:** First authenticated first-party GIS source in production, October 24, 2026. Free infrastructure; original agency evidence; source-specific controls.

## Why this path is necessary

The original `government_gis_disclosure_leads` workflow expected a government webpage to hyperlink to the exact Flock camera GIS layer. That is legitimate *one* way to prove source provenance, but it is not a universal publication pattern. Some local governments directly own/serve authoritative GIS endpoints while their public site links to an agency map portal rather than one internal ArcGIS layer.

Katoptron now supports a **second, independent original-government provenance path** for vetted, same-registrable-domain GIS servers. It authenticates the agency's government GIS homepage and the agency-owned map portal; checks that the Flock-labelled point layer is listed by the government GIS service; fetches a complete set of typed original ArcGIS ObjectIDs in two passes; confirms every matching object has one bounded geometry; and hashes the original webpage and complete point inventory. New sources are checked for overlap with the current canonical verified map. Missing, changed, unreachable or duplicative evidence fails closed.

## First live source: Alachua County, Florida

- Official government GIS homepage: https://growth-management.alachuacounty.us/GIS
- Linked government GIS portal: https://mapgenius.alachuacounty.us/
- Agency-hosted GIS layer: https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0
- Attested source key: `agency_alachua_fl`
- Individual feature identity: typed ArcGIS `objectid`, whose field name is lowercase in the source. The type and unique set are verified in the live original service; an additional `CameraID` string is not mandatory when the government labels the entire layer as Flock Cameras.
- Complete verified feature inventory: **18** Flock Cameras GIS point records.
- [Successful source attestation and profile publication #2](https://github.com/ayeemecee0/Katoptron/actions/runs/40117914128). Live production PostgreSQL was subsequently checked: **293 canonical exact verified locations**, including 18 under Alachua's source URL, one private source receipt, and one verified original government GIS authority. This is evidence of government-documented positions, **not** camera uptime, active license-plate scanning, or real vehicle observation.

## Reproducible infrastructure

- `scripts/audit_agency_hosted_gis.py`: read-only original government page + portal + GIS schema + double ObjectID list + entire bounded geometry. No private tokens or database publication, and no individual coordinates printed in public CI logs.
- `scripts/auto_register_agency_gis.py`: rechecks live proof immediately before private candidate staging and calls narrowly scoped source authorization. Existing verified sources are rechecked idempotently; changed or revoked identities are held. Adds publication only through `auto_verify_camera_profiles.sync`.
- `supabase/migrations/081_first_party_agency_hosted_gis_authority.sql`, `082_agency_arcgis_objectid_casefold.sql`: source-pinned, service-role-only DB registration; private original-page/geometry receipts; exact expected hosts, source label, geographic bounds, duplicate rejection and authentication gate.
- `scripts/auto_verify_camera_profiles.py`: independently retrieves the entire official GIS inventory and reconciles established sources; the original typed ObjectID path is allowed only for the vetted Alachua authority, not arbitrary third-party Esri layers.
- `.github/workflows/audit_agency_hosted_gis.yml`: weekly original agency metadata audit; `.github/workflows/register_agency_gis.yml`: weekly vetted registration/recheck; GitHub Actions validation and daily map health monitor enforce the 18-point baseline.

## Evidence hierarchy and remaining expansion work

1. Original government-owned GIS on verified agency-controlled domain: the new live first-party route. **An agency homepage-to-specific-layer link is not required.**
2. Government webpage directly links an exact external layer and independent ArcGIS ownership + complete original feature geometry are corroborated: existing `auto_attest_external_arcgis.py` path.
3. Approved original government documents explicitly disclose georeferenced camera locations: source-attributed, reviewer-verifiable government evidence path.
4. Independently reviewed cross-family firsthand field documentation: can qualify only for clearly labeled *provisional* evidence, not the canonical government GIS count.
5. Unverified catalog labels, social maps, copied OSM nodes, program procurement, vendor claims and ambiguous coordinates: private **candidates only**.

**The bottleneck is not fully solved nationwide:** the production generalization of source authority currently has one explicitly pinned Alachua origin. To scale safely, next build a private, original-agency GIS authority registry with per-domain review receipts, equivalent ownership and evidence recheck constraints, and controlled automatic per-agency registrations. Do not allow a random Esri owner name or unsourced GIS layer title to seed its own authority. Existing 7 third-party ESRI candidates still lack approved original government association and must not be promoted just to increase the number of pins.

Original linked-page removal, server withdrawal, service schema drift or unverifiable inventories must trigger a held/revoked source review and a **time-separated** loss-of-source check. Do not revoke current government history solely because a single network fetch timed out.

## Acceptance status

Live source publication, full map integrity, independent checked feature count, original-page proof, CI source security, public map health and private receipt monitoring passed. Manual real-device visual review and a full production restore drill are independent gates for overall Katoptron production certification.

## October 24 follow-on: reusable, independently governed agency registry

[Validation #499](https://github.com/ayeemecee0/Katoptron/actions/runs/40119773469) passed the new generic registration and review-revocation SQL suite, then migration 083 was applied to production.

- `scripts/reviewed_first_party_gis_sources.json` is a **publicly auditable and strictly validated input registry**. Its entries contain original agency GIS page, original county-operated portal, exact point layer, source key, jurisdiction, bounded geographic envelope and human-reviewed explanation. The JSON does not authorize the source by itself.
- `public.reviewed_first_party_gis_roots` is the **independent database-owner-reviewed approval gate**. Service-role automation may read approvals, but cannot insert, edit or delete them. No contributor or anonymous role can approve a government authority. The reviewed table currently contains the previously independently authenticated Alachua agency; adding another requires an individually supported owner-side approval/migration.
- `public.register_reviewed_first_party_flock_source` is **one reusable source registration function**. The live verifier must present original agency evidence, twice-confirmed stable ArcGIS feature IDs, bounded source geometry, original source digest and reviewed layer binding. A new exact layer without a vetted database-root entry cannot qualify. It cannot publish a camera by source registration alone.
- Revocation or deletion of an original reviewed approval revokes the corresponding trusted source, government GIS host authority and verification profile; current public visibility is additionally constrained by the underlying verified-source predicate.
- `scripts/audit_agency_hosted_gis.py` now obtains approved agency inputs from the reviewed JSON, uses per-agency geographic bounds (rather than Florida-only bounds) and remains read-only. `scripts/auto_register_agency_gis.py` checks the database review row and exact pinned attributes separately before attempting the generic registration RPC.
- `scripts/auto_verify_camera_profiles.py` rebinds every original government receipt to its still-approved registry row and GIS host; a typed ArcGIS ObjectID-only profile cannot inherit another agency's source key. The existing Alachua source remains published through this common authorization logic. Changes are covered by owner-bound tests and complete SQL registration tests.
- The scheduled private health workflow now requires both at least one **approved original government GIS root** and at least one **original source receipt**; loss of an approval is a live monitoring failure.

**Result:** the hardcoded registration bottleneck is removed at the application/SQL architecture layer, but automatic nationwide approval is intentionally not enabled. The remaining throughput bottleneck is researching and independently approving additional legitimate agency-operated GIS origins. Third-party vendor-hosted Esri data require their own evidence path and cannot be auto-trusted. The canonical exact point count remains 293 across seven jurisdictions.

## October 24 repeatable source-verification bottleneck audit

Source-level review has been generalized beyond the original single-county SQL via `scripts/first_party_registry.py` and database migration `083_reviewed_first_party_agency_registry.sql`. The owner-approved government-source registry is private, with independently reviewed metadata and source revocation; adding an unreviewed ArcGIS JSON item cannot authorize publication.

The **live [GIS candidate triage #1](https://github.com/ayeemecee0/Katoptron/actions/runs/40132048463)** separated the 12 remaining private GIS candidates into three duplicates of already verified GIS sources, two trusted-government-source layers whose complete 32 original point features all fell within a conservative 100 metre match radius of existing verified points, and seven externally hosted ArcGIS candidate datasets requiring independent original-government publisher evidence. No source was automatically approved just because an ArcGIS item or layer title said Flock Cameras.

The **[publisher ownership diagnostic #6](https://github.com/ayeemecee0/Katoptron/actions/runs/40132374011)** independently resolved the exact original ArcGIS item plus Esri portal/owner profile for six of seven external candidates. That confirms an accountable Esri publisher identity but **not** government operation or endorsement. The seventh organization ID remains unrecoverable from public service item / publisher profile metadata. All seven remain unpublished. Details and next original-agency verification priorities: [verification bottleneck report](./verification-bottleneck-2026-10-24.md).

The secondary optional deployment-polygon crawler encountered a persistent Newport Beach original GIS service catalog error even after one bounded retry, and correctly failed rather than inventing coverage. [P2 tracking issue](https://github.com/ayeemecee0/Katoptron/issues/1). Point-level GIS verification and publisher-link triage are separate from the optional polygon crawler and remained green.
