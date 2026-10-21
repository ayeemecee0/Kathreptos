# Katoptron (Κάτοπτρον)

Katoptron is a public-records accountability project focused on **Flock Safety** and **automated license plate recognition (ALPR)**. It documents what government agencies actually proposed, approved, contracted, or deployed, with primary-source links. It also includes a separate **synthetic surveillance simulator**. No real plate numbers or vehicle tracking are collected.

## Current project status

- **Public website:** [Katoptron on GitHub Pages](https://ayeemecee0.github.io/Katoptron/) (the simulator is on the home page).
- **Source-verified public database:** [Verified government records](https://ayeemecee0.github.io/Katoptron/records.html), backed by Supabase read-only public views and row-level security.
- **Automatic public evidence verification:** [Daily discovery workflow](./.github/workflows/discover.yml) finds official government matters, then [automatic Flock mention verification](./.github/workflows/auto_verify_agenda.yml) re-fetches live Legistar records and publishes only exact, source-verified agenda mentions with explicit Flock Safety titles. No manual click required.
- **Optional exceptions review:** [`agenda_evidence_reviews`](./supabase/migrations/006_legistar_source_integrity_and_review.sql) holds ambiguous or incomplete records. The [review dashboard](https://ayeemecee0.github.io/Katoptron/review.html) is available for difficult contract, action, or deployment claims, not required for already-proven official agenda mentions.
- **Explicit government-domain authority:** [Government-domain approval policy](./docs/official-government-domains.md) limits custom domains and ambiguous Legistar tenant aliases to individually reviewed government evidence.
- **Automated code and database checks:** [Validation workflow](./.github/workflows/validate.yml).

**Automation policy:** Public government agenda mentions with exact, re-fetched official API titles naming **Flock Safety** are published automatically. They are labelled as *agenda mentions*, never approvals, signed contracts, vendor payments, or installed cameras. The project still needs separate stronger evidence rules before safely automating those higher-level facts.

Read the [full end-to-end project audit and prioritized roadmap (October 2026)](./docs/project-audit-2026-10-21.md).

## Source integrity and publication policy

- **Discovery is not verification.** Search snippets and news reports remain private. A government agenda mention may be published automatically only after an exact live API matter match, explicit Flock Safety in the official title, and pre-verified tenant/jurisdiction identity.
- **Flock Safety is not synonymous with ALPR.** Vendor identification must be explicit in the linked primary government source.
- **An authorization is not an executed contract.** Distinguish proposed, failed, adopted, signed, deployed, superseded, and terminated statuses. Do not infer an individual's vote from an agency-level decision.
- **Original primary sources:** official government records are linked wherever available. The Legistar API's `MatterId` is not assumed to equal a public LegislationDetail page `ID`.
- **Publication is evidence-tiered.** Exact official Flock agenda mentions are verified automatically in their own restricted table. More consequential public actions, contracts and deployments still require distinct primary-source proof; the workflow service-role cannot write them as published. The optional reviewer interface remains for unresolved claims.
- **Privacy:** no private number plates, individual movement histories, personal addresses, or inferred real camera routes. All simulator vehicles, cameras, and detections are fictional.

## Repository

| Path | Purpose |
| --- | --- |
| [`index.html`](./index.html) | Synthetic simulator and clearly identified illustrative research links |
| [`records.html`](./records.html) | Live, verified public records; not the unreviewed news/agenda queue |
| [`scripts/discover.py`](./scripts/discover.py) | Unverified news leads |
| [`scripts/discover_official.py`](./scripts/discover_official.py) | Government-page discovery; **review-only** |
| [`scripts/discover_source_registry.py`](./scripts/discover_source_registry.py) | Conservative government-source and Legistar portal discovery |
| [`scripts/verify_government_sources.py`](./scripts/verify_government_sources.py) | Checks official government links, jurisdiction identity, and Legistar API access |
| [`scripts/discover_government_records.py`](./scripts/discover_government_records.py) | Bounded historical Legistar scanner, queues exact official API MatterIds |
| [`scripts/auto_verify_flock_agenda.py`](./scripts/auto_verify_flock_agenda.py) | Automatically verifies exact official Flock Safety agenda mentions from live API titles |
| [`.github/workflows/auto_verify_agenda.yml`](./.github/workflows/auto_verify_agenda.yml) | Runs after successful government discovery and on relevant updates |
| [`supabase/migrations/013_automatic_verified_flock_agenda_mentions.sql`](./supabase/migrations/013_automatic_verified_flock_agenda_mentions.sql) | Immutable verified agenda mentions, public read-only policy and exact-provenance guards |
| [`supabase/migrations/`](./supabase/migrations/) | Database schema, reviewed government-domain authority, editorial staging, and publication guards |
| [`docs/project-audit-2026-10-21.md`](./docs/project-audit-2026-10-21.md) | Full audit, known limitations, and next-step priority |

## Operations

The database is already created and connected. Migrations **003 through 013** have been applied to the existing Supabase project; migrations 001 and 002 were the initial schema setup. All new migrations are tested in a disposable PostgreSQL database before production.

To launch a new discovery run, use [Discover public Flock records](https://github.com/ayeemecee0/Katoptron/actions/workflows/discover.yml) and select **Run workflow** on `main`. The workflow runs daily on a schedule.

Only the Supabase **publishable key** is permitted in browser code. Keep the database service-role key restricted to GitHub Actions secrets and trusted server-side operations.

## Next milestone

Extend **evidence-specific automatic verification** beyond source mentions. The next useful automation would independently establish an adopted legislative action from official dated vote/action history, and then signed agreements from official executed contract documents. Do not infer those facts from agenda title text or use the optional reviewer dashboard as a prerequisite for the narrow mention feed.