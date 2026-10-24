# Milestone 5 — Community evidence submissions

Release verification: October 23, 2026 (America/Los_Angeles).
**Core engineering and browser simulation passed. A live, email-confirmed Storage API upload test remains outstanding.**

## Functionality

- `submit.html`: optional email/password registration, sign-in, private submission, latitude/longitude, observation date, description, optional original HTTPS source and up to one privately attached WebP photo per report. Photos are resized and re-encoded client-side to remove input metadata; image content is **not** automatically inspected for personal information.
- The original-photo restriction is 3 MB of input, 20 megapixels and 2,400 pixels on the longest stored side. The underlying Storage bucket is private, not public.
- Pending or `needs_evidence` reports can attach or retry a missing photo. A reporter can also add a **previously missing** HTTPS source URL once; a link cannot be overwritten after submission. The contributor is not granted review-status, consent, or owner-ID update privileges.
- Three reports per authenticated user per **rolling** 24 hours. Migration 076 repaired an earlier fixed-window loophole and retains a private per-user transaction lock.
- Reviewer-only `community-review.html`: private reports, duplicate proximity screening, original source links, short-lived photo URLs, reviewer explanation (at least 15 characters), audited outcomes and incorporation into **unverified private** evidence.
- The reviewer can mark `needs_evidence`, `rejected` or `incorporated`. Only original independent verification can qualify an incorporated candidate as an actual published camera, and **separate reporter publication consent is false by default**.
- Reporters can withdraw reports, which revokes any corresponding source candidate and attestation. The browser then requests photo deletion **through the Storage API**. Supabase deliberately prohibits deleting Storage metadata directly with SQL.
- No reporter ID, private screening result, private photo, or submission audit trail is public. Canonical government-verified cameras remain a distinct dataset.

## Database releases

Initial community migrations 060–069, followed by:
- `076_rolling_community_rate_limit.sql`: exact moving 24-hour cap with owner-locked insert count.
- `077_upload_followup_evidence.sql`: allow a requested private photo while pending or needing evidence.
- `078_fix_community_storage_column_permissions.sql`: critical Storage RLS repair. Invoker Storage policy queries originally referenced private contributor/reviewer columns that `authenticated` intentionally cannot SELECT. New policies rely on the owner-scoped report SELECT policy and pre-existing `editorial_session()` reviewer authorization. No private user-ID privileges were granted.
- `079_one_time_community_source_followup.sql`: narrowly scoped `UPDATE(original_source_url)` privilege and owner + status + null-source row-level policy. Contributor cannot modify review outcomes or publication consent.

All four releases were applied to production Supabase.

## Verification performed

**PostgreSQL transaction tests, all rolled back after execution:**
- `scripts/test_milestone5_submission_security.sql`: authenticated submissions, source screening and report limit.
- `scripts/test_community_multi_actor_lifecycle.sql`: two distinct contributors, a reviewer, owner-only reads, unauthorized action denials, reviewer audit, incorporation, revocation and rejection of unconsented public pins.
- `scripts/test_community_rolling_rate_limit.sql`: the fourth insert is denied even when the legacy bucket would have reset.
- `scripts/test_community_source_followup.sql`: cross-account source update fails; one-time owner addition succeeds; source cannot be overwritten; incorporation is still unverified and private.
- `scripts/test_community_storage_rls_production.sql`: live production Storage metadata-only role simulation, including owner and reviewer read access, prohibition on cross-account reads, followup attachment after `needs_evidence`, and prohibition on uploads following withdrawal. This does **not** upload or delete actual blob bytes. All temporary auth users, report rows, and Storage metadata were rolled back.

**Browser and deployment checks:**
- `scripts/smoke_community_authenticated_mock.cjs`: intercepted client simulation of sign-in, first report and consent defaults, image conversion and upload call, withdrawal and deletion call, additional source/photo on `needs_evidence`, approved reviewer viewing and action. The SDK and backend are mocked; **this is not an actual Supabase Auth or Storage HTTP integration test**.
- `scripts/smoke_community.cjs`: unauthenticated access checks and page availability.
- [Validate Katoptron scripts #424](https://github.com/ayeemecee0/Katoptron/actions/runs/40065151680) — success.
- [Browser release smoke #99](https://github.com/ayeemecee0/Katoptron/actions/runs/40065139953) — success.
- [GitHub Pages #675](https://github.com/ayeemecee0/Katoptron/actions/runs/40065151545) — success.

Production inspection after testing: **0 community submissions, 0 private photos, 0 community audit rows**, and the **275 canonical government-verified camera points** were unchanged.

## Genuine remaining release acceptance

An eligible human tester must confirm a real email-signup link and redirect, an authenticated upload and download of a non-sensitive photo into the private Storage bucket, and file deletion after withdrawal. A real account must never share their password or session token with a public GitHub issue or assistant chat. Do not create a fake camera sighting presented as a real submission: use actual good-faith reporting, or prepare a separately flagged private QA workflow.

Check Supabase's Auth redirect allowlist and password/email abuse settings in the owner's dashboard; API migrations and mock sessions cannot prove those external settings. Free-plan leaked-password screening is not available without a higher tier.

This feature is ready for a *controlled beta* but is not yet certified production-ready. No paid hosting resource was added.
