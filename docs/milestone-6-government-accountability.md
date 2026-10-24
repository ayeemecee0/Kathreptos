# Milestone 6 — Flock Safety government accountability

## Scope and implementation

**Implemented October 23, 2026.** Project URL: https://ayeemecee0.github.io/Katoptron/accountability.html

The public accountability directory is not a political position scorer, an individual-movement tracker, or a complete nationwide government-contract inventory. It preserves separate, narrowly substantiated factual claims.

### Source-backed evidence flows

| Category | Required proof | What can be stated |
| --- | --- | --- |
| Original government program | Source-dated government disclosure, verified citation | Program described or terminated as of source date |
| Original agenda mention | Previously verified live government API matter explicitly naming Flock Safety | Flock appeared on an official government agenda; **not an approval** |
| Recorded legislative decision | Verified governing-body action from official government history | Named legislative body recorded an action; **not an individual vote or signed agreement** |
| Editorial agency action | Owner-published action and verified public primary-source record | Only the factual reviewed description, with recorded date or clearly undated |
| Signed agreement | Independently published signed contract with a documented signature date and Flock vendor | Executed contract with supported amount where provided |
| Agreement-form PDF | Previously verified government-hosted contract-like PDF | Form and original document exist; **execution not verified** |
| Agency deployment record | Editorially verified agency report with original source | Government-reported count at a supported source date, not active camera locations |
| Vendor professional role | Original Flock Safety professional appointment / leadership announcement | Company-reported professional position **as of source date**, not proof of current employment |
| Individual public official | Original government roll-call or directly recorded government statement naming the person | Actual recorded position on the stated matter only; no inference from agency-wide results |

### Production components

- `supabase/migrations/070_accountability_evidence_feed.sql`: seven evidence types via a **security-invoker** view backed exclusively by existing published and row-level-security-filtered sources. Public access is read-only.
- `071_accountability_dated_roles.sql`: dated Flock leadership claims with original company links, original source category, review timestamps and per-row RLS. Three named public professional roles are currently included, labeled as vendor-attested claims.
- `072_accountability_de_duplicate_public_index.sql`: the public directory removes repeated legacy undated disclosures sharing the same document and agency. Original source records remain unchanged for auditing.
- `073_explicit_official_positions.sql`: verified individual roll-call / official statement schema. No publisher except a database owner can approve rows. **No individual vote has been proven or inserted**.
- `accountability.html`: public search, state/type/date filters, source citations, a dated chronological directory, CSV source export, vendor-role provenance and a separate original-government-positions area.
- `records.html` and `index.html`: link directly to the directory.
- CI: `scripts/test_accountability_m6.sql`, `scripts/test_accountability_individual.sql`, inline JS syntax validation, `scripts/smoke_accountability.cjs` and GitHub Actions.
- Discovery/evidence-maintenance budget (~10%): the existing daily public health monitor now verifies the accountability index, source URLs, confidence classifications and publisher boundaries; new unit tests cover failure cases.

### Audited production dataset at integration

- 33 raw government evidence rows, 30 deduplicated directory items: 20 government programs, 5 verified agenda mentions, 4 nonduplicate editorial actions, 1 agency-reported deployment.
- 3 source-dated vendor professional-role claims, separate from government accountability counts.
- 0 source-confirmed individually recorded votes, 0 published executed contracts, 0 qualifying automatic legislative decisions and 0 qualifying contract PDFs in the existing production data. **Zero means none documented in Katoptron's current verified dataset; it does not mean zero nationwide.**
- All synthetic SQL examples used during verification ran inside rolled-back transactions. No fictional officials, votes or contracts were saved.
- Program disclosures or vendor employment do not establish surveillance deployment in a municipality.

### Acceptance validation

The production PostgreSQL checks passed:

- Anonymous callers read only publication-eligible rows; source tables' RLS remains in force.
- No public/anonymous ability to write roles, official votes, publication evidence, or editorial decisions.
- A synthetic unverified individual vote was invisible to anonymous readers.
- Both new SQL regression suites passed in the live Supabase database.
- Static JavaScript syntax parsing passed for the accountability page.

**Still to independently confirm before release acceptance:** the latest GitHub Pages deployment result, the completed GitHub Actions code/browser jobs, and an actual live headless browser run against the published site. The available GitHub connector in this session cannot enumerate non-PR workflow run conclusions. Do not claim these passed until observed. The database is live and the source repository is committed.

### Design constraints

No addresses, plates, personal travel histories, or unofficial individual voting inferences. A current verified government source means a provenance-backed factual claim at its source date, not an exhaustive census or an assurance of current operation. Monitoring failures are alerts, not permission to manufacture evidence.
