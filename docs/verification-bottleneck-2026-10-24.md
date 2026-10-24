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

## Independent original-government-to-Esri organization link search

The zero-cost [original government Esri endorsement workflow #2](https://github.com/ayeemecee0/Katoptron/actions/runs/40133019083) passed its original-agency link and ownership regression tests and read-only live audit:

- **22 original agency pages read successfully**, one page unavailable;
- **six exact original ArcGIS publisher organizations identified** from the externally hosted Flock layer's original service item and publisher profile;
- **none of the 22 original government pages linked the matching ArcGIS organization** through the restricted organization-ID or verified Esri organization portal URL forms;
- one external ArcGIS layer still has no independently recoverable organization identity; and
- **zero new sources approved and zero cameras published**.

This is a real evidence bottleneck, not a code failure. Org names are self-asserted on Esri: an account whose title sounds governmental is not authority to label private map pins as police-operated Flock cameras. The newly introduced [government-to-Esri link probe](../scripts/probe_original_gov_arcgis_org_links.py) runs weekly with bounded original-government pages. It will surface an authenticated publisher-relationship lead if new original agency records start disclosing the correct Esri organization, without inferring installed camera locations.

**Highest-leverage next source expansion:** prioritize independent same-domain government GIS inventories from newly vetted agencies and original public documents with exact installation locations; expand the original source registry when authenticated, and keep separately treating unendorsed third-party Esri/OSM nodes as provisional private leads. Do not spend repeated full verification cycles on the three redundant layers or two overlapping source wrappers.

## Secondary maintenance finding

[Government deployment polygon workflow #6](https://github.com/ayeemecee0/Katoptron/actions/runs/40132616090) remains red because the original Newport Beach GIS service-root catalog still does not return a valid layer listing after a bounded retry. This affects the optional original deployment-polygon crawler, not the independently verified public GIS camera point inventory. The persistent source issue is tracked at [GitHub issue #1](https://github.com/ayeemecee0/Katoptron/issues/1). Previously published camera points must not be revoked solely on this separate polygon discovery failure.

## October 24 targeted original-government publisher evidence expansion

The [targeted publisher search #7](https://github.com/ayeemecee0/Katoptron/actions/runs/40134228772) added exact `ArcGIS Feature Service` item-link verification as a separate independent government evidence path, in addition to existing government links to the publisher organization itself. Esri item ID, type, original service URL and individual item owner must all be confirmed from the original publisher before a matching link on a freshly fetched original `.gov` HTML page can even count as a government-association **research lead**.

The search now uses bounded Bing RSS with independent DuckDuckGo fallback, rotating three private Esri candidate sources per run (twice weekly), refusing non-government search results, redirects, false item IDs and over-budget crawling. Live audit checked **three uniquely identified original Esri Feature Service items** and encountered **four original government search results**; **none** linked the exact independent candidate publisher. One original government page could not be fetched. Zero cameras published; verified point baseline remains **293**. This proves the remaining original government endorsement obstacle is real, rather than silently declaring a publisher official based on its Esri account name.

The workflow outputs short hashes rather than the private candidate URLs or geographic coordinates; its source and item ownership checks have offline regressions. Other official agency source research and first-party GIS registry approvals remain separate. Search snippets and Esri organization display names are never agency approval.

## October 24 periodic original-publisher evidence integrity

A new owner-bound [original government GIS recheck #12](https://github.com/ayeemecee0/Katoptron/actions/runs/40134625191) passed against the existing approved Alachua source. It independently re-fetched the government's GIS page/portal, confirmed complete stable original ArcGIS ObjectIDs and features, and updated a private append-only recheck receipt (migration 084). The live database confirmed **one recheck-history event**, a fresh original publisher proof, and **293** canonical points. The RLS/privilege probe verified anonymous users and contributors cannot read or advance these receipts; only the existing server-side verification role can invoke the narrowly scoped refresher.

The daily [private data health monitor #8](https://github.com/ayeemecee0/Katoptron/actions/runs/40134746504) passed after adding a separate **21-day stale original-publisher warning**. Camera geometry freshness does not substitute for original government publisher evidence freshness. A failed original page load does *not* silently revoke camera history on a single transient outage; it prevents the independent provenance timestamp from advancing and eventually triggers an operational alert.

**Nationwide approval remains evidence-gated.** These features reduce the verification tooling bottleneck and make stale attribution observable but do not invent original government endorsements for the seven pending third-party hosted ArcGIS sources.


## October 24: complete original-GIS inventory and queue convergence

A live production audit confirmed **293 exact government-source camera records**,
**seven trusted GIS source datasets**, **12 unverified GIS source candidates**,
**one reviewed first-party source registry entry**, and **14 private original-government
GIS search pages**. None of the 14 pages held exact GIS service/layer links at
the time checked; no new camera records were promoted.

The national camera-source verification bottleneck now has two tested resilience
improvements:

1. **Exact ArcGIS inventories, not maximum-record-count guesses.**
   Both original-.gov camera registration and derived approved-host registration
   request the complete authoritative `returnIdsOnly` snapshot, retrieve all
   exact ObjectIDs in bounded batches, reject duplicate/missing/mismatched features,
   and require an unchanged second source inventory. ArcGIS `maxRecordCount`
   truncation can no longer be mistaken for successful complete coverage.
2. **Government disclosure lead-to-verifier bridge.**
   The original-government GIS-link research worker now sends only freshly
   fetched, same-.gov-apex, exact camera GIS layer links from Flock-specific
   government disclosures to the existing private nationwide verification queue.
   Search hits, custom-domain layers, and external Esri items do not inherit
   source authority; the existing registration stage independently checks the
   live page and exact GIS geometry again before granting trust.

The public Github Actions loggers for both registration paths now use hashed
candidate identities and sanitized error classifications in place of private
candidate URLs or database error response bodies. No private report coordinates,
unverified GIS URLs, or database credentials should be logged by these paths.

**Acceptance tests:** [source-verifier validation #545](https://github.com/ayeemecee0/Katoptron/actions/runs/40136162725),
[new original government registration #14](https://github.com/ayeemecee0/Katoptron/actions/runs/40136162714),
[derived government registration #11](https://github.com/ayeemecee0/Katoptron/actions/runs/40136040171),
[government GIS disclosure discovery #9](https://github.com/ayeemecee0/Katoptron/actions/runs/40135830538).
These pass for the committed source and unit tests; they do **not**
establish any new government agency publisher endorsement.

**Next evidence acquisition priority:** seek additional original-agency GIS
inventories that document Flock-specific camera points and independent government
publisher ownership, or exact original-government endorsement for the existing
external ArcGIS candidates. Preserve uncertain candidate records privately.
No extra paid infrastructure was provisioned.


## October 24: original-disclosure text coverage and resilient GIS links

An additional release improved source discovery without accepting unverified camera
coordinates. A government disclosure may now describe **"Flock cameras"** instead
of the exact brand phrase "Flock Safety". The source crawler checks original
HTML *prose outside anchor tags* for a Flock camera program before even
staging a private GIS lead. A hyperlink labelled "Flock cameras" on an otherwise
unrelated government map index is explicitly insufficient.

The original government link worker also recognizes same-government-apex ArcGIS
`MapServer` / `FeatureServer` **service directories** as private research
leads. The independent verifier must still resolve a unique exact Flock-labelled
point layer and check original page, source ownership, camera identities, geometry,
a complete immutable ObjectID inventory and duplication before any public record
could be created. External Esri service directories are not admitted by this route.

The first-party original-domain comparator was additionally hardened for
delegated United States government/public suffix namespaces like `wa.us`
and `co.us`. Separate agencies sharing a state-level suffix must never
inherit each other's approved source-publisher identity. The same comparator
is enforced in both the reviewed registry validator and live first-party
agency GIS audit.

**Passed release evidence**:
- [Original-government GIS discovery #15](https://github.com/ayeemecee0/Katoptron/actions/runs/40136782396)
- [Full script validation #554](https://github.com/ayeemecee0/Katoptron/actions/runs/40136782387)
- [GitHub Pages #852](https://github.com/ayeemecee0/Katoptron/actions/runs/40136782263)
- [First-party agency source verification #12](https://github.com/ayeemecee0/Katoptron/actions/runs/40137090864)
- [Full script validation #558](https://github.com/ayeemecee0/Katoptron/actions/runs/40137090857)
- [GitHub Pages #856](https://github.com/ayeemecee0/Katoptron/actions/runs/40137090877)

The latest public-government discovery scan inspected **eight** reachable
original source pages and held **one** unreachable agency page. There were
**zero new government camera GIS links** and no source approvals. Live database
reconciliation afterward still found **293 exact source-verified points**,
**seven trusted datasets**, **12 private unverified datasets**, **zero**
original-government search pages with qualifying GIS links, and **one**
reviewed first-party agency receipt.

A public Brookhaven, Georgia government GIS service was also investigated as
a potential source. Its `PD/FlockMap_BaseLayers` service documents map base
layers / police beats, *not a Flock camera point inventory*, so it cannot
add verified cameras. Do not equate an application's Flock name with a
source-supported camera dataset.

**Unchanged acceptance blockers:** additional distinct original-government
camera point inventories or independent publisher endorsements; owner-held
private backup recovery validation (including Auth and Storage); a real
authenticated browser upload/reviewer/withdrawal acceptance test; Geoapify
account configuration verification; and independent real-device accessibility
testing. Supabase linter INFO notices for deliberately private RLS tables
without public policies are not permission failures. Do not add broad public
RLS policies simply to make that advisory disappear.

No new paid hosting was provisioned. Maintain the approximately 10% discovery
maintenance share and the exact-source / non-operational-status warnings.


### Final discovery pass: delegated namespaces and state-rotation wording

Further validation covers nested delegated local-government and school-domain
namespaces such as `district.k12.wa.us`, ensuring unrelated agencies cannot
be treated as one original map publisher merely because they share a public
suffix. The reviewed GIS source record is still separately bound by an
owner-approved database authority row.

The zero-cost nationwide crawler now alternates the government-search
wording used for each state's successive 10-day cycles: "Flock Safety"
and "Flock cameras". The fifty-state rotation and independent original
source-page checks remain unchanged; this only increases the variety of
evidence leads investigated. No search-engine snippet authorizes a camera pin.

Production readiness remains explicitly **beta**, not an assertion of complete
nationwide coverage or current live camera operation.
