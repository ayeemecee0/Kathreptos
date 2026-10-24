# Milestone 9 — Production launch gates and incident response
Status as of October 23, 2026: engineering safeguards implemented; **not approved for full production**.

## Deployment policy
Katoptron is a public evidence-first beta. Full production requires evidence integrity, a documented privacy posture, monitored routing reliability, site accessibility and verified CI runs. Missing cameras are unknown, not absent. Neither public historical source disclosures nor simulated encounters reveal actual license-plate detections.

## Delivered low-cost operational controls

| Control | Implementation | Status |
| --- | --- | --- |
| Production source health | Daily `.github/workflows/monitor_public_health.yml` checks deployed map, source rechecks, canonical GIS counts, source provenance and accountability/analytics reconciliation | Implemented; [health monitor #24](https://github.com/ayeemecee0/Katoptron/actions/runs/40063811128) passed |
| Browser release smoke | `.github/workflows/browser_smoke.yml`: local push and published-site Chromium map, routing, community portal, accountability, analytics, keyboard/mobile checks | Implemented; [browser smoke #91](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928164) passed |
| Postgres security regression | `.github/workflows/validate.yml`: SQL migrations, RLS boundary tests, original government verification rules, discovery tests, JS/static accessibility checks | Implemented; [validation #407](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928191) passed |
| Public evidence snapshots | Weekly `.github/workflows/snapshot_public_evidence.yml` gathers **anonymous-only** published evidence, reconciles counts and hashes content, 7-day artifact retention | Implemented; not a backup of private Supabase tables |
| Public factual corrections | GitHub Issue template `.github/ISSUE_TEMPLATE/evidence_correction.yml`; prominent warnings against private details | Implemented |
| Source provenance | Original government, agency, vendor-claimed roles and uncertain community reports kept distinct; source withdrawals revoke appropriate public evidence | Implemented in earlier milestones |
| Routing failure | Frontend reports routing/geocoding unavailability rather than a surveillance-free route | Beta behavior, production provider SLA unproven |
| Financial exposure | GitHub Pages + existing Supabase project + public Geoapify client; no additional paid infrastructure provisioned | Existing quota/overage behavior must be confirmed externally |

## Critical remaining production gates

1. **CI deployment evidence**: **Completed for this release:** [validation #407](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928191), [browser smoke #91](https://github.com/ayeemecee0/Katoptron/actions/runs/40063928164), [health monitor #24](https://github.com/ayeemecee0/Katoptron/actions/runs/40063811128) and public snapshot #1 succeeded. Continue treating these workflows as mandatory for every subsequent release.
2. **Authenticated browser acceptance**: confirm a real registration and confirmation, private evidence/photo upload, reviewer decision and report withdrawal without exposing a reporter's identity or a non-consenting point. Use an expendable test account and clear records afterward.
3. **Provider controls**: verify Geoapify's public-key allowed referrers/origins (if supported) and daily usage/overage controls. The key is browser-visible; repository comments must not claim origin protection without dashboard proof. Production routing requires reliable provider capacity and availability, not anonymous demo infrastructure.
4. **Auth protection**: Supabase advisor reports leaked-password detection not enabled. **Supabase documents this feature as Pro-plan-and-above only, so it is NOT a free-tier prerequisite.** While staying Free, set strong minimum password length and complexity in the project's Auth Email settings and verify email confirmation/abuse controls. Reconsider leaked-password protection when finances allow. Never add auth secrets to GitHub Pages.
5. **Postgres privileged function review**: security advisor flags 4 anonymous-callable and 15 authenticated-callable SECURITY DEFINER functions. Some may be intentional source-lookup/reviewer RPCs; audit arguments and minimum grants against caller behavior before changing a function that existing RLS uses.
6. **Backup and restore**: weekly public snapshots are **not** recovery backups. Establish a Supabase database + Storage backup with private data encrypted, access controlled, retention policy, and an actual restore drill before trusting private community submissions in production. Never upload private community reports into public GitHub Actions artifacts.
7. **Independent accessibility**: screen-reader, 200% zoom, contrast, external map keyboard and real mobile device testing to a documented WCAG target. Automated smoke is not certification.
8. **Operational/privacy review**: retention and deletion procedure for photo objects, public map inaccuracies, incident notifications, third-party route data, and terms of service. Coverage remains sparse nationally.

## Incident severity and response

- **P0: private data leak or false public verified evidence.** Disable/revoke the affected public view or individual record under source-specific rollback where possible; disable offending frontend exposure; preserve relevant source and SQL audit trail; assess scope; do not publish a claim that the problem is contained without requerying anon permissions. Notify affected users according to applicable obligations.
- **P1: routing outage, stale source provenance, broken signup.** Show 'unavailable/unknown'; keep the rest of the evidence map read-only; inspect GitHub Actions, provider response codes and Supabase logs; investigate per-source before publication.
- **P2: documentation/UI regression, noncritical delayed discovery.** Record in GitHub Issue tracker, repair with test and independent source recheck. Continue spending about 10% of engineering effort on discovery, stale source validation and evidence maintenance.

## Free-tier confidential recovery procedure

A [private backup and local restore runbook](./free-tier-private-backup-recovery.md) now documents Supabase Free-plan logical exports and the separate Storage object backup requirement. The published-data GitHub archive cannot restore private account records, and **no private production backup or real restore drill has been performed yet**. Owner-controlled local encryption and credentials are required.

## Rollback and recovery

- Static frontend regression: revert to last verified GitHub `main` revision, wait for a verified GitHub Pages deployment, rerun browser/health checks.
- Erroneous published source: mark source-specific evidence withdrawn using its existing reviewed authority procedures, then verify anon reads exclude it. Never simply delete the only original review/audit trail.
- Database DDL mistake: apply a reviewed **forward** corrective migration with a temporary canary and explicit permission tests; do not assume reverting a Git commit rolls back production Postgres. Restore only from verified encrypted backups under authorized control.
- Suspected credential abuse: rotate any compromised provider or service credentials via their owner consoles, review quota and logs, and ensure no service-role credential was ever copied into static HTML.
- Prioritize privacy and preservation of evidence provenance over uptime claims.

## Cost posture and owner actions

No paid infrastructure added for this milestone. Free-tier limits and unbounded public-provider usage may still create service failure or charges depending on owner account settings; the hosting provider must confirm those terms. Human account/dashboard actions will be required for provider-key controls, free-plan Auth strength/email safeguards, and a private database restore setup. Leaked-password protection requires a paid Supabase tier and is intentionally deferred. Release gate remains **BLOCKED** until these are resolved and live acceptance tests pass.

## Next engineering milestones

Use maintenance/analytics telemetry to improve national official-source coverage and evidence correctness. New sources must follow the independent verification architecture and cannot be promoted merely from community reports, news, or vendor-advertised material. A fully nationwide inventory is not a realistic sign-off requirement while official camera data remain unavailable; missing records are labeled unknown.

## October 24 owner backup checkpoint and production boundary monitoring

The owner completed the manual Supabase CLI `db dump` export locally on an encrypted Windows computer: `roles.sql`, `schema.sql`, `data.sql` were all nonempty and passed simple keyword/content presence checks. **These private files were not uploaded, opened by Katoptron maintainers, or restore-tested.** They are application-schema/data exports, not a complete Auth or Storage-blob backup; the private recovery gate remains open.

The scheduled production health workflow now probes anonymous requests to private reports, evidence, reviewer registries and sensitive RPCs with only the public browser key. [Health #27](https://github.com/ayeemecee0/Katoptron/actions/runs/40109111232) passed with 10 private boundaries denied: seven private table reads plus three safe non-mutating reviewer RPC calls tested by POST with valid argument signatures. The previous GET-based RPC probe was insufficient because volatile functions can reject GET even if executable. No private response bodies were read. Reviewer write-RPC privileges remain enforced by the mandatory PostgreSQL release test. This complements, but does not replace, production SQL grants/RLS tests.

Other production blockers remain: actual credentialed email/Storage acceptance, an authorized restore drill, full Auth/Storage backup, real-device assistive-technology tests, and Geoapify account-side origin/referrer key restrictions and quota monitoring. Supabase dashboard-only controls cannot be validated by a frontend mock.

## October 23 production-hardening acceptance

- [Validation #440](https://github.com/ayeemecee0/Katoptron/actions/runs/40066618103) passed the required release boundary checks. These deny anonymous reads/writes on private community data, preserve editor-only writes, catch unaudited editor RPC grants, reconcile camera evidence totals, and alert if new unreviewed anonymous privileged functions appear.
- [Browser smoke #108](https://github.com/ayeemecee0/Katoptron/actions/runs/40066618279) passed. New trip planning clears the prior street route, camera proximity totals and replay controls **before** trying an external routing request. Failed replacements do not display the former trip's camera results.
- [Private offline backup runbook](./free-tier-private-backup-recovery.md) is implemented but **not executed**. A trusted owner machine, database credentials, encrypted local/offsite storage, and a real local restore drill are required; the 7-day GitHub public snapshot does not protect private records or Storage object bytes.
- Supabase database size was approximately 33.4 MiB when queried. Free-tier database and provider quotas still need operational alerts as adoption grows.
- Browser Supabase SDK is version-pinned to `2.118.0` in contributor and editorial pages. This is a supply-chain hardening measure, not a promise of immunity from CDN compromise.

## October 24 release verification and discovery posture

- [Validation #451](https://github.com/ayeemecee0/Katoptron/actions/runs/40109111201) passed and [Browser #114](https://github.com/ayeemecee0/Katoptron/actions/runs/40108637053) passed map, route, contributor mock, reviewer mock, mobile, keyboard and zoom-equivalent checks. Real Geoapify was also checked from the deployed GitHub Pages origin using fixed public Sacramento/Folsom fixtures.
- Latest read-only data inspection: 275 source-verified exact camera points across six jurisdictions, 11 unverified GIS source candidates, and 8,186 unverified independent camera candidates. Raw candidate counts are not camera counts, agency-confirmed points or vetted nationwide coverage. Discovery maintenance remains approximately 10% of engineering effort; focus the remaining 90% on source authentication, simulator integrity, private evidence acceptance and launch safety.
- Controlled launch remains conditional on an actual Auth/Storage E2E test, local encrypted backup restore exercise, provider account-side key restrictions, and manual assistive-technology review. No paid infrastructure added.

## October 24 — Automated recovery rehearsal (validated)

- **[Validation #454](https://github.com/ayeemecee0/Katoptron/actions/runs/40112397254) passed**, including `scripts/rehearse_ci_application_restore.sh`. GitHub Actions creates a disposable PostgreSQL source populated by existing migrations and synthetic data, uses `pg_dump` to create a custom-format logical export, restores that full app fixture into a second disposable PostgreSQL database, and independently verifies roles, private contributor ownership, anonymous denials, government source baselines, source reference integrity and no publication of unconsented fictional camera sightings. Cleanup removes the temporary database and backup after the run.
- This **does not restore or upload the owner's Windows backups**. The synthetic `auth.users` table in CI is a minimal stub, not a genuine Supabase Auth backup; private Storage blob contents are absent. This is an application-side restore test, **not** an operational production-disaster recovery signoff.
- Existing local `roles.sql`, `schema.sql`, `data.sql` were user-confirmed present, non-empty and structurally recognizable. They remain private on the user's encrypted Windows drive. A controlled full Auth and Storage backup, confidential off-device retention and a real local restore rehearsal are still blocked on owner-controlled credentials/files.
- The latest nationwide GIS discovery and corroboration workflows remain automatically scheduled; candidate datasets remain private until original-source validation. Maintaining the discovery pipeline remains the planned 10% engineering allocation.


## October 24 — Private photo and discovery safety

- A new cost-free scheduled read-only [private Storage / discovery conversion monitor #1](https://github.com/ayeemecee0/Katoptron/actions/runs/40113188567) passed. It uses the existing server-only GitHub secret, verifies the actual production bucket is **private**, enforces its 3 MiB image-only restrictions, and collects database totals exclusively using `HEAD` responses (no candidate or report row payloads).
- Production conversion baseline: **275 verified canonical exact points**, **10,399 unverified candidate camera records**, **11 unverified candidate GIS sources**, **14 original-government GIS research pages**, **0 direct government GIS receipts**, **0 externally approved authorities**, **10 independent matching records** (not newly approved cameras). The bottleneck is legitimate source authentication, not raw candidate collection. A zero-verified-link condition warns without inventing a source or claiming camera absence.
- The live community Storage bucket had **0 photo objects** when inspected. Migration 080 gates reviewer reads on non-withdrawn report status; the reporter can still list a withdrawn report's attachments for deletion retry. The dedicated rollback-only production Storage SQL test passed after the migration. Already-minted signed URLs can remain valid until expiry, so new reviewer links use 60-second TTL.
- **Not cleared:** owner backup Auth/Storage restore and off-device private storage; real browser signup/upload/download/delete acceptance; independent dashboard-level service-key quota controls and genuine assistive-technology review. No paid hosting was provisioned.

## October 24 — Verified government GIS source expansion, evidence safeguards

One government-verified county source was added using a new independent first-party provenance path. The official original Alachua GIS page, agency portal and layer share the agency-controlled county domain, but the page does not have to include a direct link to the exact Flock camera layer. The original Flock-only government GIS metadata, typed stable object IDs and all complete georeferenced points were fetched and double-checked. Strict database source pinning, original page/feature receipts, no possible existing camera duplicates, separate private candidate staging and universal source reconciliation remain mandatory.

- [Successful automatic first-party registration #2](https://github.com/ayeemecee0/Katoptron/actions/runs/40117914128): **18 original-agency camera point GIS records published**, **275 existing points rechecked**, **0 errors**, **0 withdrawals**. Live PostgreSQL subsequently verified **293** exact canonical source-verified points, 18 new Alachua records, one private original agency receipt and 0 private submissions.
- [Public monitor #29](https://github.com/ayeemecee0/Katoptron/actions/runs/40118272067) passed the increased seven-jurisdiction **293** reviewed baseline; new independent original-government jurisdiction regression alerts on loss/staleness.
- [Private Storage / discovery guard #3](https://github.com/ayeemecee0/Katoptron/actions/runs/40118279893) passed with **293** exact camera points and **one** first-party original-government GIS receipt, using aggregate HEAD requests only. No candidate row data, private photos or credentials were written into CI logs.
- Other government GIS catalog links without independent original government source ownership remain unpublished. A nationwide, governed source-root registry is still necessary to generalize beyond the single pinned source; this is the highest-priority expansion work. Camera source operation and vehicle plate reads remain unknown; output is **source-documented historical locations**.

All operations used existing GitHub Actions, GitHub Pages and Supabase resources; no new paid infrastructure or private user photographs.
