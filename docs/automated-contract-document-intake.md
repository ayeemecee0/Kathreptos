# Automated official Flock contract-document intake

## Scope and operational status

This is the **primary-document evidence phase** of the executed-contract verifier, not the executed-contract verifier itself.

Daily discovery verifies government authority and exact Flock Safety agenda-title identity. Once the [automatic agenda verifier](../.github/workflows/auto_verify_agenda.yml) succeeds, [this workflow](../.github/workflows/auto_verify_contract_documents.yml) automatically:

1. Refreshes the exact government Legistar matter and original title, file number, municipality and verified trust binding.
2. Retrieves the government's current list of matter attachments from the read-only official Legistar API.
3. Reads only public HTTPS PDFs served by the verified municipality's exact Legistar host, with redirect restrictions, max 8 MiB, max 60 pages, bounded total scan, and no OCR guesses.
4. Looks in the **document body itself**, not the agenda headline, for the literal vendor name *Flock Safety*, a formal agreement-opening phrase, contract/legal clauses, and the actual contracting municipality.
5. Publishes a source URL, PDF SHA-256 fingerprint, byte count, page count and government reference into a distinct public **contract documents** category. This claims document presence and content only.
6. Does not overwrite existing evidence. If a previously verified attachment's content hash changes, withdraws its publication until separately reverified. Source or agenda revocation also withdraws dependent documents.

The table's \`execution_status\` is hard-coded to \`not_verified\`, including for documents with signature blocks. It is deliberately **not** the existing \`contracts\` or \`published_contracts\` table.

## Important limitations

- **An attached PDF is not proof of an executed contract.** A signature block may be blank, a copy may be a draft or vendor template, and a government resolution may authorize but not sign an agreement.
- The scanner skips scanned or image-only PDFs without machine-readable text, pages hosted on unapproved outside domains, non-PDF links, unrecognized formal agreement formats, downloads that fail or redirect to another provider, and PDFs whose municipality is not textually identified.
- A qualifying PDF does not establish effective date, consideration actually paid, vendor performance, license plate reader installation or individual officials' votes.
- A digital signature's cryptographic validity and the authority of both parties' actual signers are not yet independently corroborated. **No executed-contract row will be auto-published by this stage.**
- Results may be zero: zero means the current verified matter/attachment sample did not satisfy the strict checks, not that there are no Flock agreements in a municipality.

## Next required stage: executed-contract proof

Implement a separate, narrowly scoped verifier that confirms the specific signed agreement (including both contracting parties, actual signatures or independently verifiable executed status, and the executed date) using official records or cryptographic document verification. Only then permit a distinct \`verified_flock_executed_contracts\` record, with evidence-level classification and correction handling. Expand verified government document hosts based on independently confirmed government authority rather than relaxing URL checks.

The optional review dashboard is for exceptions; routine collection and conservative evidence publication require no human approvals.


## October 21 observed production URL formats / supported host trust

The initial scan saw **20 current government attachment references** across
five verified Legistar matters but accepted none because only
\`{tenant}.legistar.com\` was permitted. Live government API metadata showed:

- \`oakland.legistar1.com/oakland/attachments/{uuid}.pdf\` (11)
- \`costamesa.legistar1.com/costamesa/attachments/{uuid}.pdf\` (3)
- \`legistar.granicus.com/Commerce/attachments/{uuid}.pdf\` (4)
- \`legistar1.granicus.com/mountainview/attachments/{uuid}.pdf\` (2)

Migration 017 and the updated verifier accept these **exact scoped forms**
only when returned by a freshly checked official API matter. The hostname
alone is insufficient: cross-jurisdictional tenant paths, non-UUID names,
query-string variants and redirects to unapproved hosts fail closed.

Additional city-hosted PDF links are permitted only if the host is present
in the existing **owner-reviewed** \`official_government_domains\` registry
with exactly matching tenant and jurisdiction, including explicit \`allow_www\`.
New \`.gov\` or \`.com\` sites are never approved from search snippets.
The database independently enforces the platform/municipal-host rules.

The main GitHub validation workflow installs \`pypdf\` through
\`requirements.txt\`; the initial test suite failure was caused by
the PDF parser being omitted from that dependency manifest.


## First corrected production scan and classification

The first scan with verified platform-host support validated all **20 official
attachment URLs**, with no rejected links or network download errors. None
could be classified as an original Flock-specific *agreement* from their
extractable PDF text.

- 10: no clear agreement-form body/clauses (mostly presentations, policy
  records, reports and legislation)
- 7: no explicit vendor name in machine-extracted PDF text; importantly,
  this includes an attachment titled "Flock User Agreement" and **the title
  alone is not sufficient proof of the contents**
- 2: encrypted PDFs are held
- 1: PDF parsing dependency error. The dependency manifest now installs
  \`pypdf[crypto]\` to support permitted crypto codecs, but any encrypted PDF
  remains held until it can be independently and safely verified

This scan did **not** produce a false signed-contract or payment claim.
Rather than loosen the proof standards, the next meaningful coverage
work is government-hosted **executed agreement/contract repositories**,
with explicit execution proof independent of agenda titles.
