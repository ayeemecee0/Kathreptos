# Katoptron (Κάτοπτρον)

Katoptron is a public-records accountability project focused on **Flock Safety** and **automated license plate recognition (ALPR)**. It documents what government agencies actually proposed, approved, contracted, or deployed, with primary-source links. It also includes a separate **synthetic surveillance simulator**. No real plate numbers or vehicle tracking are collected.

## Current project status

- **Public website:** [Katoptron on GitHub Pages](https://ayeemecee0.github.io/Katoptron/) (the simulator is on the home page).
- **Source-verified public database:** [Verified government records](https://ayeemecee0.github.io/Katoptron/records.html), backed by Supabase read-only public views and row-level security.
- **Private source discovery:** [Daily discovery workflow](./.github/workflows/discover.yml) gathers candidate news leads and scans only verified government Legistar tenants.
- **Private editorial review:** [`agenda_evidence_reviews`](./supabase/migrations/006_legistar_source_integrity_and_review.sql) stores verifiable API matter references, preserved historical URLs, source-specific notes, vendor attribution, and reviewer decisions.
- **Explicit government-domain authority:** [Government-domain approval policy](./docs/official-government-domains.md) limits custom domains and ambiguous Legistar tenant aliases to individually reviewed government evidence.
- **Automated code and database checks:** [Validation workflow](./.github/workflows/validate.yml).

**Current development bottleneck:** the project has a substantial backlog of private discovered leads and only a small collection of published, fully checked records. The next feature should be a **private reviewer interface and repeatable evidence-to-publication workflow**, not further indiscriminate scraping.

Read the [full end-to-end project audit and prioritized roadmap (October 2026)](./docs/project-audit-2026-10-21.md).

## Source integrity and publication policy

- **Discovery is not verification.** Search snippets, news articles, Legistar API title matches, and proposed legislation are held for review.
- **Flock Safety is not synonymous with ALPR.** Vendor identification must be explicit in the linked primary government source.
- **An authorization is not an executed contract.** Distinguish proposed, failed, adopted, signed, deployed, superseded, and terminated statuses. Do not infer an individual's vote from an agency-level decision.
- **Original primary sources:** official government records are linked wherever available. The Legistar API's `MatterId` is not assumed to equal a public LegislationDetail page `ID`.
- **Publication requires editorial review.** The daily discovery workflow does **not** auto-publish newly found sources. Supabase guards block the GitHub service-role credential from marking public sources verified or inserting/modifying published facts.
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
| [`scripts/discover_government_records.py`](./scripts/discover_government_records.py) | Bounded historical Legistar scanner, queues API matter IDs rather than constructing incorrect HTML page IDs |
| [`supabase/migrations/`](./supabase/migrations/) | Database schema, reviewed government-domain authority, editorial staging, and publication guards |
| [`docs/project-audit-2026-10-21.md`](./docs/project-audit-2026-10-21.md) | Full audit, known limitations, and next-step priority |

## Operations

The database is already created and connected. Migrations **003 through 009** have been applied to the existing Supabase project; migrations 001 and 002 were the initial schema setup. New migrations should be tested in the validation workflow's disposable PostgreSQL database before applying them in production.

To launch a new discovery run, use [Discover public Flock records](https://github.com/ayeemecee0/Katoptron/actions/workflows/discover.yml) and select **Run workflow** on `main`. The workflow runs daily on a schedule.

Only the Supabase **publishable key** is permitted in browser code. Keep the database service-role key restricted to GitHub Actions secrets and trusted server-side operations.

## Next milestone

Build a private, authenticated review interface that displays each queued item beside its **correct government document**, lets a reviewer classify Flock-specific versus general ALPR content, records the actual proposal/approval/execution status, and allows deliberate audited publication of narrowly supported claims. Keep unverified material out of public views.