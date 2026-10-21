# Katoptron automated government-record verification

## Production behavior

Katoptron is **automatic by default for facts that meet a narrowly defined
primary-source standard**. No reviewer needs to use the dashboard or click
Publish for those records.

The [daily discovery job](../.github/workflows/discover.yml) finds and queues
candidate government Legistar matters. On successful completion,
[automatic agenda verification](../.github/workflows/auto_verify_agenda.yml)
retrieves official government API matters independently and automatically
publishes only qualified official **Flock Safety agenda mentions** in a
dedicated [public records view](../records.html).

The automation also runs whenever its workflow or verifier implementation
is updated, and can be triggered manually for maintenance. Duplicate findings
are ignored rather than republished.

## What qualifies without a human

Every automatically published agenda mention must pass all checks:

1. **Verified government authority:** the matching Legistar tenant was
   verified through the government's official website or a specifically
   reviewed custom government-domain binding.
2. **Exact primary-source identity:** a live HTTPS request to the official
   `webapi.legistar.com/v1/{tenant}/matters/{MatterId}` endpoint returns
   the **same integer MatterId** that was staged in Katoptron's private
   queue. Search snippets and news links are not accepted as proof.
3. **Explicit vendor name in the official title:** the returned
   `MatterTitle` or `MatterName` must directly name **Flock Safety**.
   Generic "ALPR" or "license plate reader" records do not qualify.
4. **Public information only:** matters explicitly restricted from web view
   or marked deleted are held.
5. **No editorial veto:** a previously rejected matter, or one already
   published as a reviewed action, is not republished automatically.
6. **Exact-source provenance:** the public record contains the official
   API URL, exact official title, jurisdiction, file number and a government
   authority evidence URL. The latter is checked against the private,
   verified government source registry.
7. **No overwrite:** the workflow may insert a new verified agenda mention,
   but cannot overwrite or delete existing publications.

These produce one exact claim: **an official government agenda matter
explicitly mentions Flock Safety**. This record type does **not** claim
approval, councilmember position, executed contract, payments, or
installation of cameras.

## What does not auto-publish

A Flock-related **presentation** does not establish a contract. An
"approve contract" **staff recommendation** is not necessarily an adopted
council action. An **adopted authorization** is not necessarily a signed
agreement. A generic **license plate reader** agenda item may involve a
different vendor.

The next automation tiers should verify these *separately* from richer
primary sources (dated legislative action histories, signed agreements,
purchase orders, budget/payment documents and agency-reported deployments).
Do not promote ambiguous statements just to increase published counts.

No further news scraping is necessary to achieve the current agenda-mention
automation. Incomplete candidates can stay private indefinitely. The
[private reviewer dashboard](../review.html) is an **optional exception
queue**, not a required approval bottleneck.

## Source revocation

[Migration 013](../supabase/migrations/013_automatic_verified_flock_agenda_mentions.sql)
creates the public read-only verified mention table and exact-provenance
insertion checks.

[Migration 014](../supabase/migrations/014_revoke_auto_mentions_on_source_revocation.sql)
automatically revokes dependent published mentions when the verified government
tenant or a domain-to-tenant authority binding loses its verified status.
Revoked records are hidden from public reads but preserved internally for audit.

## Audit and diagnostics

Inspect the GitHub Actions job logs from
[Auto-verify official Flock agenda mentions](../.github/workflows/auto_verify_agenda.yml)
for:

- `Independently verified government tenants eligible for auto-check`
- `Private agenda matters checked for automatic exact-title verification`
- `Official Flock Safety agenda mentions confirmed against live API`
- `New exact-title government agenda mentions auto-published`
- `Existing verified agenda mentions skipped`
- `Agenda matters held for incomplete/ambiguous evidence`

The CI workflow exercises the same matter-ID/vendor checks and checks database
revocation, record immutability and anonymous read-only access using a
disposable PostgreSQL database.

Do not add user-generated claims, votes, contracts or camera locations to
this automated mention table. New automated fact categories require their
own evidence model and regression tests.
