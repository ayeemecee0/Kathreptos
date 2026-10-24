# Milestone 5 — Community evidence submissions
Updated 2026-10-23.

## Functional delivery

- Public submission page: `submit.html`, backed by Supabase email/password Auth. Anonymous inserts are rejected.
- Report fields: US coordinates, description, observation date, optional original HTTPS source, contributor review consent.
- Limit: three submissions per signed-in account in a rolling **fixed 24-hour bucket**. Account creation is not rate-limited by Katoptron's application, so abuse protection should be revisited at scale.
- Private photographs: file-size cap of 3 MB, accepted JPG/PNG/WebP input, client-side re-encoding to WebP to discard input metadata, maximum source image 20 MP and longest stored side 2,400 px. Storage bucket is private and per-report.
- Automatic staging: reports with an original source URL enter the tiered evidence database **as candidates only**. Neither report entry nor duplication screening counts as independent source authentication.
- Screening: private approximate-coordinate lookup for nearby reports or existing verified points; does not publish a claim or assign calibrated probability.
- Approved reviewer access: `community-review.html`, reviewer allowlist, private queue, short-lived attachment URLs, required decision rationale, audited actions. A reviewer's `incorporated` decision means private research incorporation, **not** official verification.
- Contributor access: own status history and withdrawal. Withdrawal/rejection revokes the related source attestation and staged point. The browser attempts to erase the contributor's Storage photo objects after withdrawal.
- Public separation: no anonymous grants on submission/triage/audit tables, no contributor approval grants, no change to the 275 original canonical cameras. Existing evidence-reconciliation rules must still independently validate evidence before any publication.

## Implemented migrations

`060` through `068` under `supabase/migrations/`. All nine migrations were applied to the Katoptron Supabase project.

## Verified production database checks

- Authenticated insert: successful in a rolled-back transaction.
- Daily report limit: the fourth report failed; all synthetic records rolled back.
- Private screening trigger: inserted report creates screening.
- Private candidate staging with external source URL: source attestation is staged, not reviewed.
- Approved reviewer: report accepted for private incorporation with an audit row; withdrawal revokes candidate. Synthetic test records rolled back.
- Rejected reviewer outcome: case and attestation rejected; public tiered map count for the test source remained zero.
- Anonymous insert, anonymous reviews and unapproved reviewer access: denied.
- Bucket is nonpublic.

## Automated regression and UI checks

`scripts/test_milestone5_submission_security.sql` checks SQL intake, screening, caps, private candidate staging and reviewer rejection on PostgreSQL CI. `scripts/test_community_frontend_syntax.py` validates both inline scripts. `scripts/smoke_community.cjs` verifies both anonymous-entry pages in Chromium and is integrated into `browser_smoke.yml`.

## Release acceptance not yet confirmed

- GitHub Actions/Pages latest run conclusion has not been read. Committing code does not itself prove the Pages deployment passed.
- Authenticated browser end-to-end proof of signup, actual photo storage, approved reviewer access, and private photo withdrawal has not been performed; completing this requires test credentials in a permitted environment. Do not use a private owner password in source code.
- Image moderation is based on user consent and client-side metadata stripping, **not** automatic detection of faces, plate numbers or personal information.
- Existing organization-wide Supabase security-advisor warnings should be reviewed separately before a high-traffic launch.

This is an engineering-complete beta feature with release acceptance still pending, **not** a fully verified production launch. No paid hosting resource was provisioned.
