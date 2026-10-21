# Automatic legislative-decision verifier

## Production status

**Active**. Katoptron automatically runs
[`auto_verify_legislative_decisions.py`](../scripts/auto_verify_legislative_decisions.py)
after a successful
[official Flock agenda verification workflow](../.github/workflows/auto_verify_agenda.yml).
The job uses the independent, read-only Legistar API and source-verified
government registry. No dashboard clicks are required.

Workflow: [Auto-verify Flock legislative decisions](../.github/workflows/auto_verify_decisions.yml).
Public display: [Verified public records](../records.html) →
**Auto-verified legislative decisions**.

The first production run checked 9 verified Legistar sources and the
5 eligible official Flock-title matters, yielding **0 new qualifying decisions**.
This is an evidence outcome, not an execution error. The public feed only
includes events meeting every criterion below.

## Exactly what can be published automatically

A government legislative event qualifies only if ALL of the following hold:

1. The Legistar tenant is on the independently verified government registry.
2. The specific matter was previously verified from the live Legistar API,
   its official title directly names **Flock Safety**, its identity matches
   a preserved `MatterId`, and no reviewer has rejected it.
3. The verifier **re-fetches the matter** and confirms its title and file
   number are unchanged. It also fetches the official
   `/v1/{tenant}/matters/{MatterId}/histories` records.
4. One history entry has a stable integer `MatterHistoryId`, unambiguous
   `MatterHistoryActionName` (exactly *Adopted*, *Adopted as Amended*,
   *Approved*, *Approved as Amended*, *Failed*, or *Rejected*),
   a compatible `MatterHistoryPassedFlagName` (*Pass/Passed*
   or *Fail/Failed*), an accepted **full legislative governing-body**
   name, and a credible explicit action date.
5. The exact tenant, matter ID, history ID, official title, body, named
   action, result and action date match the bounded PostgreSQL schema
   checks and verified parent government source. Every published event
   has a direct, deterministic official API history URL.

A committee recommendation, staff presentation, introduction, discussion,
first reading, committee referral, ambiguous/missing vote status, different
vendor, unsupported action body, conflicting history ID, or changed
government title **cannot** become a citywide adopted/failed decision.

## Important interpretation limits

These are **discrete historical action events**, not necessarily the
ultimate final status of a proposal. Several events can exist for one matter.
For each, the site says which legislative body took exactly what named action
on what date.

A recorded adoption or approval **does not** prove that an agreement was
executed, money was paid, or cameras were installed. No individual official's
vote, attendance, support or opposition is inferred here. Those require a
separate explicit source (roll call, signed contract, payment record, etc.).

The already reviewed Oakland December 2025 adopted-as-amended resolution
remains a separately published editorial record; the verifier does not
manufacture a second auto-approved claim for it.

## Security

[Migration 015](../supabase/migrations/015_auto_legislative_decisions.sql)
adds a dedicated public-read-only table, with role-limited inserts, immutable
provenance, rejection of conflicting action and result fields, and a foreign
key to already verified Flock government agenda matters.

The GitHub workflow's service-role credential can insert a new separately
corroborated event, **but cannot rewrite or delete** published event facts.

If the original verified matter is revoked, dependent legislative events
are automatically marked revoked and hidden from anonymous/public views.
Source trust revocation also cascades through the existing public agenda
trust system.

The verifier has a bounded live history scan, refuses conflicting duplicate
event IDs, and fails closed on missing or oversized/unavailable API responses.
Regression tests cover genuine vs. misleading outcomes, incompatible flag
names, wrong governing body, metadata changes, unsupported matter IDs,
date bounds, no contract/vote inference and idempotency.

## Diagnostics and acceptance criteria

The job prints:
- Verified government authority bindings
- Currently verified explicit-Flock official matters
- Private matters staged for action-history verification
- Source-corroborated legislative action events
- New government legislative events auto-published
- Previously verified legislative events skipped
- Explicit Flock matters without provable legislative outcomes
- Government histories held due to errors

Use `python scripts/auto_verify_legislative_decisions.py --dry-run --show-actions`
to inspect live public Legistar action-field coverage without writing
to Supabase. This is useful before expanding accepted action vocabularies.

**No manual review is required to operate the above automatic flow.**
The private review dashboard remains an exception tool for claims
that cannot meet these strict evidence rules.

## Next project milestone

Automated **executed-contract** verification from signed government
contracts or equivalent authoritative records, with an explicit distinction
between a recommended contract, an adopted authorization, and a fully
executed agreement. Do not infer amounts or deployments from an agenda title.
