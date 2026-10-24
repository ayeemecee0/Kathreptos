# Milestone 9 — Production launch gates and incident response
Status as of October 23, 2026: engineering safeguards implemented; **not approved for full production**.

## Deployment policy
Katoptron is a public evidence-first beta. Full production requires evidence integrity, a documented privacy posture, monitored routing reliability, site accessibility and verified CI runs. Missing cameras are unknown, not absent. Neither public historical source disclosures nor simulated encounters reveal actual license-plate detections.

## Delivered low-cost operational controls

| Control | Implementation | Status |
| --- | --- | --- |
| Production source health | Daily `.github/workflows/monitor_public_health.yml` checks deployed map, source rechecks, canonical GIS counts, source provenance and accountability/analytics reconciliation | Implemented; current run outcome must be independently confirmed |
| Browser release smoke | `.github/workflows/browser_smoke.yml`: local push and published-site Chromium map, routing, community portal, accountability, analytics, keyboard/mobile checks | Added; latest run outcome not retrieved |
| Postgres security regression | `.github/workflows/validate.yml`: SQL migrations, RLS boundary tests, original government verification rules, discovery tests, JS/static accessibility checks | Added; latest run outcome not retrieved |
| Public evidence snapshots | Weekly `.github/workflows/snapshot_public_evidence.yml` gathers **anonymous-only** published evidence, reconciles counts and hashes content, 7-day artifact retention | Implemented; not a backup of private Supabase tables |
| Public factual corrections | GitHub Issue template `.github/ISSUE_TEMPLATE/evidence_correction.yml`; prominent warnings against private details | Implemented |
| Source provenance | Original government, agency, vendor-claimed roles and uncertain community reports kept distinct; source withdrawals revoke appropriate public evidence | Implemented in earlier milestones |
| Routing failure | Frontend reports routing/geocoding unavailability rather than a surveillance-free route | Beta behavior, production provider SLA unproven |
| Financial exposure | GitHub Pages + existing Supabase project + public Geoapify client; no additional paid infrastructure provisioned | Existing quota/overage behavior must be confirmed externally |

## Critical remaining production gates

1. **CI deployment evidence**: inspect GitHub Actions for a green latest `Validate Katoptron scripts`, `Browser release smoke`, `Monitor public map health`, and `Archive public evidence snapshot` run. Do not infer passing from committed workflows or an empty commit-status response.
2. **Authenticated browser acceptance**: confirm a real registration and confirmation, private evidence/photo upload, reviewer decision and report withdrawal without exposing a reporter's identity or a non-consenting point. Use an expendable test account and clear records afterward.
3. **Provider controls**: verify Geoapify's public-key allowed referrers/origins (if supported) and daily usage/overage controls. The key is browser-visible; repository comments must not claim origin protection without dashboard proof. Production routing requires reliable provider capacity and availability, not anonymous demo infrastructure.
4. **Auth protection**: Supabase advisor reports leaked-password detection not enabled. Review whether available in the account tier, enable if available, and consider email deliverability/abuse controls. Never add auth secrets to GitHub Pages.
5. **Postgres privileged function review**: security advisor flags 4 anonymous-callable and 15 authenticated-callable SECURITY DEFINER functions. Some may be intentional source-lookup/reviewer RPCs; audit arguments and minimum grants against caller behavior before changing a function that existing RLS uses.
6. **Backup and restore**: weekly public snapshots are **not** recovery backups. Establish a Supabase database + Storage backup with private data encrypted, access controlled, retention policy, and an actual restore drill before trusting private community submissions in production. Never upload private community reports into public GitHub Actions artifacts.
7. **Independent accessibility**: screen-reader, 200% zoom, contrast, external map keyboard and real mobile device testing to a documented WCAG target. Automated smoke is not certification.
8. **Operational/privacy review**: retention and deletion procedure for photo objects, public map inaccuracies, incident notifications, third-party route data, and terms of service. Coverage remains sparse nationally.

## Incident severity and response

- **P0: private data leak or false public verified evidence.** Disable/revoke the affected public view or individual record under source-specific rollback where possible; disable offending frontend exposure; preserve relevant source and SQL audit trail; assess scope; do not publish a claim that the problem is contained without requerying anon permissions. Notify affected users according to applicable obligations.
- **P1: routing outage, stale source provenance, broken signup.** Show 'unavailable/unknown'; keep the rest of the evidence map read-only; inspect GitHub Actions, provider response codes and Supabase logs; investigate per-source before publication.
- **P2: documentation/UI regression, noncritical delayed discovery.** Record in GitHub Issue tracker, repair with test and independent source recheck. Continue spending about 10% of engineering effort on discovery, stale source validation and evidence maintenance.

## Rollback and recovery

- Static frontend regression: revert to last verified GitHub `main` revision, wait for a verified GitHub Pages deployment, rerun browser/health checks.
- Erroneous published source: mark source-specific evidence withdrawn using its existing reviewed authority procedures, then verify anon reads exclude it. Never simply delete the only original review/audit trail.
- Database DDL mistake: apply a reviewed **forward** corrective migration with a temporary canary and explicit permission tests; do not assume reverting a Git commit rolls back production Postgres. Restore only from verified encrypted backups under authorized control.
- Suspected credential abuse: rotate any compromised provider or service credentials via their owner consoles, review quota and logs, and ensure no service-role credential was ever copied into static HTML.
- Prioritize privacy and preservation of evidence provenance over uptime claims.

## Cost posture and owner actions

No paid infrastructure added for this milestone. Free-tier limits and unbounded public-provider usage may still create service failure or charges depending on owner account settings; the hosting provider must confirm those terms. Human account/dashboard actions will be required for provider-key controls, Supabase Auth protection and a private database restore setup. Release gate remains **BLOCKED** until these are resolved and live acceptance tests pass.

## Next engineering milestones

Use maintenance/analytics telemetry to improve national official-source coverage and evidence correctness. New sources must follow the independent verification architecture and cannot be promoted merely from community reports, news, or vendor-advertised material. A fully nationwide inventory is not a realistic sign-off requirement while official camera data remain unavailable; missing records are labeled unknown.
