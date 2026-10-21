# Katoptron private editorial review dashboard

**Optional exception handling:** Clearly identified official Flock Safety agenda mentions are verified and published automatically by the separate [official-source verification workflow](./automatic-official-verification.md). No user needs to approve these mentions in this dashboard. Use the private dashboard when evidence is insufficient for a higher-stakes factual claim, such as council adoption, signed contract or deployment.


**Dashboard:** https://ayeemecee0.github.io/Katoptron/review.html

The HTML is hosted on GitHub Pages, but the contents of the private queues,
official-source review notes, and decision history can be read only by
explicitly approved Supabase Auth user IDs. A public visitor can download the
HTML but cannot retrieve private records or invoke editorial functions.

## First-time account setup

1. Open the dashboard and choose **Create account** with an email and strong
   password. If this Supabase project requires email confirmation, confirm
   the account from the Supabase Auth email, then **Sign in**.
2. If the confirmation link redirects to the wrong location, the project owner
   must add the exact callback
   `https://ayeemecee0.github.io/Katoptron/review.html` to
   **Supabase Dashboard → Authentication → URL Configuration → Redirect URLs**.
   This is an Auth project setting, not a repository secret.
3. Once signed in, an unapproved account sees **Reviewer permission required**
   and its authenticated **user ID**. Click **Copy account ID** and give that
   UUID to the Katoptron project owner. **Do not share passwords or access
   tokens.**
4. The owner authorizes that exact Supabase Auth user ID with role
   `publisher` or `reviewer` using their trusted Supabase administrative
   connection. The user then clicks **Check access again**.
5. Authorization is *not* automatic on signup. There are no default reviewers
   or open-access administrative accounts.

The project owner can ask the connected ChatGPT Supabase integration to approve
the UUID; no day-to-day SQL editing is required. The first owner approval is an
intentional one-time administrator action.

## What each role can do

- **Reviewer:** See the private government agenda and other-leads queues,
  inspect official Legistar matter metadata, attachments, meeting history and
  original source links, save notes, classify source/vendor/outcome, approve
  evidence *privately*, reject invalid items, and reopen rejected items.
- **Publisher:** Everything a reviewer can do, plus deliberately publish a
  narrowly described, independently verified government decision. Publishing
  is a separate confirmation and requires an explicit Flock reference, an
  exact matching public Legistar page, a real event date and a completed,
  source-backed claim.
- **Unapproved logged-in account:** Cannot read private queues or use review
  RPC functions.
- **Anonymous public visitor:** Cannot call the editorial RPCs or read private
  review tables.

Even publishers cannot create public executed-contract records from a
legislative authorization in this UI. Only a documented council action can be
published; signed contracts require their own independent evidence workflow.

## Review workflow: government agenda matter

1. Choose **Government agenda matters**, select a matter, and inspect
   **Official Legistar API matter**, title, file number, GUID, attachments,
   and meeting-action history. The browser document reader uses a
   Supabase Edge Function that accepts only a registered private review ID,
   not an arbitrary URL.
2. Find the correct public **LegislationDetail** record and compare its
   title, file number, jurisdiction, and GUID with the official API matter.
   `MatterId` in the API is **not** assumed to be the public web page ID.
3. Choose topic, vendor association, actual proposal/vote/report outcome,
   action date, and a **narrow factual claim**. Use notes for caveats and
   questions. General ALPR is not proof of a Flock Safety relationship.
4. **Save draft** to preserve private work, or **Approve evidence (private)**
   after verifying the documents. Rejection requires a reason. Both actions
   are audit-logged.
5. Only a publisher can subsequently use **Publish reviewed decision**;
   the database checks current verified-tenant status, matching Legistar
   record URL, explicit Flock identification, decision date, and prior
   review. This creates a published *government action*, not a signed
   contract or a claim about installed camera counts.

The user interface checks the GUID of the reviewed government source page
against the Legistar API record, and the database also checks official
host, GUID/ID URL structure, reviewer role and prior review state. The
human reviewer remains responsible for comparing substantive document content.

## Review workflow: other discovered leads

Use **Other discovered leads** to process news articles and additional
candidate records. Link a primary government source, classify whether it
mentions Flock or only generic ALPR technology, and save or reject it.

**Accept lead (private)** means a lead is worth further research. It does
**not** create a verified source, a public decision, a contract, or a
deployment record.

Search filters the currently displayed page. The server provides paginated
queue results for the full backlog.

## Data security and audit trail

- Supabase row-level security and explicit table-level revocations apply to
  all reviewer, queue, and audit tables.
- The browser stores only Supabase's **publishable** key. No service-role or
  database-owner secret is in public HTML or the evidence Edge Function.
- Editorial RPCs check `auth.uid()` against
  `public.editorial_reviewers`. All reviewer decisions log actor ID, event,
  previous state, new state and key changes.
- Changing an approved matter's classification using Save Draft clears its
  approval; subsequent publication requires approval again.
- Review updates compare expected revision timestamps to prevent silent
  overwrites by concurrent reviewers.
- Published decisions are immutable via the dashboard. Corrections and
  revocations require a separate editorial workflow.
- A database safeguard blocks GitHub Actions' service-role account from
  independently verifying and publishing public facts.

## Technical implementation

- UI: [`review.html`](../review.html)
- Secure Auth / RPCs: [migration 010](../supabase/migrations/010_editorial_dashboard_auth_and_rpc.sql)
- Other-leads review and audit history: [migration 011](../supabase/migrations/011_general_lead_review_and_audit.sql)
- Original government evidence reader:
  [`review-evidence` Edge Function](../supabase/functions/review-evidence/index.ts)
- CI security and page syntax tests:
  [`validate.yml`](../.github/workflows/validate.yml)

No manual SQL edits are necessary to classify, approve or reject findings after
the one-time account authorization.
