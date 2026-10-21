# Katoptron end-to-end project audit
_Date: 2026-10-21 UTC. Scope: GitHub `main`, live Katoptron Supabase project, latest discovery runs, public static pages, and a sample of primary government records._

## Decision

**The next strategic milestone is a private, usable editorial review-to-publication workflow, not more unreviewed source discovery.** Discovery already outpaces reviewed and useful public records. Source identification and pagination work; increasing their volume will only compound a 500+ item review backlog.

The most urgent correctness defect was that the Legistar Web API `MatterId` was incorrectly used as the public LegislationDetail page `ID`. **That has now been fixed in the scanner and repaired for all 16 legacy agenda leads.** Their historical generated links are preserved privately for audit.

The second major trust issue was unattended auto-publication. The scheduled workflow is now **discovery-only**, and database triggers block the workflow service-role from independently verifying or publishing public fact records.

## System snapshot

| Component | Audit status |
| --- | --- |
| GitHub repository | `ayeemecee0/Katoptron` on `main`, GitHub Pages build enabled |
| Database | Supabase active, row-level security (RLS) enabled on source and editorial tables |
| Source registry | 9 verified Legistar tenants and 7 unverified Legistar candidates |
| Reviewed government domain/alias registry | 5 bindings, explicit tenant/jurisdiction rules |
| Private discovery queue | 508 items: 492 unreviewed, 15 in review, 1 accepted |
| Structured Legistar editorial review queue | 16 matters: 13 need primary-source checks, 2 source verified but not published, 1 published |
| Published government actions | 7, including 1 newly published Oakland council authorization |
| Published contracts | 0; authorizations and recommendations do **not** imply execution |
| Published deployments | 1, an agency-reported Shakopee camera count; `as_of_date` is currently unset |
| Verified public source rows | 4 |
| Public jurisdictions represented in database | 4 |

These are point-in-time counts, not national coverage statistics. The queue contains news leads, government leads and duplicate reports, not 508 vetted records.

## Trust and safety rules

1. Distinguish **Flock Safety** by explicit primary-source attribution. The words "ALPR" or "license plate reader" alone do not establish Flock as a vendor or operator.
2. Distinguish **presentation, proposal, recommendation, failed motion, adopted council authorization, executed/signed agreement, and deployed systems**. They are different factual statuses.
3. Do not infer individuals' political positions or votes from city-wide actions; only use explicit roll-call votes or recorded statements.
4. Do not infer camera installation from a recommended or approved purchase; do not infer signed contracts from council authorization.
5. Link each public claim to the *correct* official government record. For Legistar WebAPI matter IDs, use the exact official API endpoint as the deterministic machine source; include a human-readable legislative document only after independent identity matching.
6. Never publish license plates, individual movement histories, private addresses, or live person/vehicle tracking. The simulation remains synthetic and separate from factual records.
7. Publication requires editorial review and a verified source. The workflow credential is blocked by database triggers from public source verification and published fact inserts/edits.

## What was fixed during this audit

- **Source URL integrity:** `scripts/discover_government_records.py` no longer generates `LegislationDetail.aspx?ID={MatterId}` URLs. It saves `https://webapi.legistar.com/v1/{tenant}/matters/{MatterId}` as the official API reference until the corresponding public webpage is identified independently.
- **Legacy repair:** Migration 006 updated all 16 existing agenda queue URLs without losing entries, kept the original URLs in the private review table, and created a trigger to stage future Legistar API leads automatically.
- **Evidence review:** Migration 007 recorded individual notes for 16 leads, matched three to their actual public government pages, and deliberately held 13 with unresolved source or vendor status.
- **First checked publication:** Migration 008 published **only** Oakland's Dec. 16, 2025, *adopted-as-amended* Flock-related council authorization (File 26-0294), with its correct public Legistar page. It is classified as `contract_approval`, **not** an executed contract.
- **Automatic publishing disabled:** The daily GitHub workflow no longer calls `auto_publish_official.py`, and `discover_official.py` queues newly found .gov pages rather than publishing them.
- **Defense in depth:** Migration 009 prevents the GitHub service-role identity from marking `sources` verified or inserting/modifying published `actions`, `contracts`, and `deployments`. Database-owner editorial publishing remains available.
- **Website labeling:** The home page now visually distinguishes illustrative research links from the separate live, reviewed database. Example exports are labelled unverified.
- **Validation:** CI exercises migration 001–009 in disposable PostgreSQL, tests legacy link repair, review staging, manual publication and service-role blocking, and runs Python unit tests.

## Three independently reviewed initial agenda examples

| Matter | Verified primary document | Appropriate interpretation |
| --- | --- | --- |
| Oakland File 26-0189 | [Official Legistar legislative record](https://oakland.legistar.com/LegislationDetail.aspx?From=RSS&GUID=AB0429C5-392C-4E03-9941-48F2C952BA0A&ID=7704374) | Earlier proposal **failed**; never claim a signed Flock contract from this item |
| Oakland File 26-0294 | [Official Legistar legislative record](https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357) | Later resolution **adopted as amended** Dec. 16, 2025; authorizes Flock agreement, but execution/deployment are not established |
| Costa Mesa File 24-068 | [Official Legistar staff report/agenda](https://costamesa.legistar.com/LegislationDetail.aspx?GUID=83DDFC82-A148-4F71-A8FE-30577AFD0FA6&ID=6576097) | Staff recommendation for a Flock camera lease and maintenance contract; page status alone is not an adopted vote |

The remaining 13 agenda matters are not yet independently classified as published Flock decisions. An Insight Public Sector ALPR procurement in Cook County cannot automatically be described as a Flock purchase because other ALPR vendors and resellers exist.

## Remaining architectural gaps and prioritized roadmap

### P0 — Next development milestone: editorial review console and repeatable source verification

**Highest priority.** Reviewers currently need direct SQL or raw queue inspection. Build a private authenticated reviewer interface or similarly secure operator workflow that shows queued claims, API metadata, real government source attachments, candidate category, vendor identity, action/outcome, dates and clear approval/rejection buttons. Publication must be a deliberate, logged owner action. The private `agenda_evidence_reviews` table is a first foundation, **not** a finished review UI.

Prioritize the remaining 13 agenda items with explicit Flock mentions and primary staff reports or adopted meeting minutes; keep general ALPR legislation separate. Add a private evidence-to-publication mapping and recorded reviewer identity for every new public record.

**Acceptance criteria:** An operator can open a lead, inspect a verified government record, decide whether it is a Flock record, record proposal/approval/execution outcome, and publish a narrow dated fact. Unverifiable leads remain private; unaccepted sources never enter public views.

### P1 — Contract and decision documentation

The public database currently has **zero** independently published signed Flock contract records. Source-check existing official Flock contracts and add verified contract rows only when the signed agreement or equivalent conclusive government documentation proves actual execution. Capture term, award amount, renewal status and agency only when directly documented. Create chronological, distinguishable records for changes and failed proposals.

**Acceptance criteria:** Publish a small set of genuinely verified Flock-specific contract/decision records, each showing a primary-source link, precise status and date, not just a presentation headline.

### P1 — Public data experience

The site has two experiences: a **synthetic surveillance simulator** and a **source-verified records page** (`records.html`). Before this audit the home-page records tab displayed a separate hardcoded five-example dataset, including vendor-authored material, and labelled its export "verified." The link and labels have been corrected but the architectural split remains.

**Next:** Make live database records the primary content discovery pathway; add filters for agency, state, vendor linkage, record type, proposal/approved/signed status and source date. Clearly distinguish agency-reported numbers from independently documented contract terms. No synthetic simulation output should ever appear as real ALPR locations.

### P2 — Quality/maintenance of existing published seeds

The original three agencies produce **six similar published program-description actions**, because a seed migration and automation both populated them. Audit and consolidate duplicates without losing evidence; consider a dedicated agency-program record type instead of generic `other` government actions. Add an `as_of_date` for the seven-camera Shakopee record if the original agency report supports a date, and periodically recheck current sources for changes. Avoid labeling all previously added seed records independently audited until checked.

### P2 — Discovery coverage after the review backlog is under control

- Agenda scanner searches a bounded 2,000 recent/historical matters per verified Legistar tenant, with smaller pages when API replies exceed the 1.5 MB limit.
- Some official sites return 401/403/404 or exceed response-size caps; hold for manual review rather than bypassing access controls.
- Several Legistar tenants remain unverified; never auto-approve based solely on domain guessing, search snippets or Legistar tenant prefixes.
- A later backfill can use older date periods and better government portal search prioritization after editorial capacity improves.
- Do not increase raw news collection as a priority while the unreviewed queue remains over 400.

### P2 — Durable review provenance

Add review change history, independent secondary source links, specific supporting excerpts, and an attachment snapshot/hash when licensing permits. Source corrections, revocations, superseded legislation and withdrawn proposals should be representable without deleting the historical audit trail.

### P3 — Operational improvements

Update README and deployment documentation, add database migration reproducibility from a clean project, include public-site smoke checks and scheduled reporting on actual **new reviewed and published records** rather than raw leads. Existing scheduled workflow currently publishes zero new facts by design.

## Recommended execution order

**Next:** implement an authenticated private review dashboard and carry the remaining high-priority Flock-specific leads through evidence verification. **Then:** publish documented executed contracts or additional reviewed decisions. **Then:** improve the public evidence-browsing experience. Return to nationwide discovery expansion and simulator enhancements after these core accountability features.

This is an evidence-first public-records project. Success is measured by **correctly sourced public decisions and contracts**, not the number of news links or Legistar candidates found.
