# Official government-domain trust registry

Katoptron uses a private Supabase allowlist for government-operated custom
websites that do not use the .gov top-level domain.

## Initial setup (one time)

1. Open the existing Katoptron project at https://supabase.com/dashboard.
2. Select SQL Editor, then New query.
3. Open migration 003: ../supabase/migrations/003_official_government_domains.sql
4. Copy all the SQL into the editor and click Run.
5. Confirm the query reports success.

The migration creates public.official_government_domains (private via RLS)
and seeds three evidence-reviewed government websites:

- cityofmadison.com — Madison, Wisconsin — madison.legistar.com
- c3gov.com — Commerce City, Colorado — commerce.legistar.com
- slco.org — Salt Lake County, Utah — slco.legistar.com (historical)

The Salt Lake County entry has no current approved HTML evidence page and
does not automatically verify the historical Legistar portal.

## Verification policy

- An independent government source must substantiate control of a custom domain.
- A reviewed record binds the exact host to one jurisdiction and Legistar tenant.
- Only the registered apex host and explicitly allowed www variant are trusted.
- A site directly linking to a tenant is not proof that it owns every linked tenant.
- Before promoting a Legistar source, the verifier still checks a live HTTPS
  government evidence page with a matching direct link and jurisdiction identity.
- Candidate government domains never become verified from search results.
- No agenda record or contract is automatically published by this process.

## Approve a new domain (database owner only)

First locate a credible official source, such as a state-government directory
on .gov that names the government entity and its official website. Then find
a live HTML page on that exact website that links directly to the correct
Legistar tenant. Independently confirm the state and jurisdiction.

In Supabase SQL Editor, execute a reviewed insertion like this example
AFTER replacing every placeholder with confirmed values:

~~~sql
insert into public.official_government_domains
  (domain, jurisdiction_label, legistar_tenant, legistar_evidence_url,
   allow_www, verification_status, evidence_url, reviewed_by, reviewed_at,
   review_notes)
values
  ('example-city.org', 'Example City, ST', 'examplecity',
   'https://www.example-city.org/meetings',
   true, 'verified', 'https://state.gov/official-government-directory',
   'Manual review by project owner', now(),
   'Verified exact government identity and matching Legistar link');
~~~

Do not execute this example without substituting real reviewed evidence.
For an existing candidate/rejected entry, inspect its prior review decision
before updating it; do not blindly overwrite an existing status.

The GitHub workflow's service-role credential is explicitly prevented
from approving new domain authority by a database trigger.

## Revoke trust

Execute in the Supabase SQL Editor:

~~~sql
update public.official_government_domains
set verification_status = 'rejected',
    review_notes = 'Revoked after manual review'
where domain = 'example-city.org';
~~~

Replace example-city.org with the real registered domain. The next workflow
run will no longer crawl the revoked domain, and the agenda scanner will stop
scanning approved sources that relied on it. Revocation does not by itself
delete previously published records.

## Monitoring

The discovery logs report:
- Explicitly verified custom government domains loaded
- Legistar candidates with government evidence
- Newly verified Legistar tenants

The GitHub Actions validation workflow performs Python compile checks,
security regression tests, and executes the SQL migration in a temporary
PostgreSQL database before the production discovery workflow runs.

Never publish the Supabase service-role key or grant anonymous access to the
private registry.
