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
