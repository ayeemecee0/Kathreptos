-- Private, explicitly reviewed government-domain authority registry.
-- Neither web-search results nor the source discovery workflow can mark domains verified.
-- Apply in the Supabase SQL Editor before running the updated discovery workflow.

create table if not exists public.official_government_domains (
  domain text primary key
    check (domain ~ '^[a-z0-9-]+(\.[a-z0-9-]+)+$'
           and domain ~ '\.(com|org|net|us)$'),
  jurisdiction_label text not null check (length(trim(jurisdiction_label)) >= 5),
  legistar_tenant text check (legistar_tenant is null or legistar_tenant ~ '^[a-z0-9-]{3,40}$'),
  legistar_evidence_url text check (legistar_evidence_url is null or legistar_evidence_url ~ '^https://'),
  allow_www boolean not null default false,
  verification_status text not null default 'candidate'
    check (verification_status in ('candidate','verified','rejected')),
  evidence_url text,
  reviewed_by text,
  reviewed_at timestamptz,
  review_notes text,
  discovered_at timestamptz not null default now(),
  check (verification_status <> 'verified' or
    (legistar_tenant is not null and
     evidence_url is not null and evidence_url ~ '^https://' and
     nullif(trim(reviewed_by), '') is not null and
     reviewed_at is not null))
);

create index if not exists official_government_domains_status_idx
  on public.official_government_domains (verification_status);

alter table public.official_government_domains enable row level security;
revoke all on public.official_government_domains from anon, authenticated;

-- Defense-in-depth: workflow service-role credentials may discover candidate
-- domains, but cannot grant domain authority even if a future script has a bug.
-- Run deliberate approvals in the Supabase SQL Editor as the database owner.
create or replace function public.guard_official_government_domain_approval()
returns trigger
language plpgsql
set search_path = pg_catalog
as $government_review_guard$
begin
  if current_user = 'service_role' then
    if tg_op = 'INSERT' then
      if new.verification_status = 'verified' then
        raise exception 'Government domain approval requires a database-owner review';
      end if;
    elsif tg_op = 'UPDATE' then
      if new.verification_status = 'verified'
          and old.verification_status is distinct from 'verified' then
        raise exception 'Government domain approval requires a database-owner review';
      end if;
    end if;
  end if;
  return new;
end;
$government_review_guard$;

drop trigger if exists official_government_domain_approval_guard
  on public.official_government_domains;
create trigger official_government_domain_approval_guard
before insert or update on public.official_government_domains
for each row execute function public.guard_official_government_domain_approval();

-- Initial operator-reviewed entries. Authority records (on state .gov pages)
-- independently corroborate that each domain belongs to this government.
-- A verified domain is NOT permission to trust all Legistar links on its pages:
-- the approved tenant identifier must also match before a source can be verified.
insert into public.official_government_domains
  (domain, jurisdiction_label, legistar_tenant, legistar_evidence_url, allow_www, verification_status,
   evidence_url, reviewed_by, reviewed_at, review_notes)
values
  ('cityofmadison.com', 'Madison, WI', 'madison',
   'https://www.cityofmadison.com/council/district10/blog/2021-11-22/city-of-madison-website-navigation-tips-legistar', true, 'verified',
   'https://lobbying.wi.gov/Who/Principals/2021REG/ReportExport?flag=true&outRpt=PDF',
   'Katoptron evidence review, 2026-10-20', now(),
   'Wisconsin state lobbying directory identifies www.cityofmadison.com as the City of Madison website; official City Council pages link madison.legistar.com.'),
  ('c3gov.com', 'Commerce City, CO', 'commerce',
   'https://www.c3gov.com/Government/City-Council/Council-Voting-Records', true, 'verified',
   'https://dnrweblink.state.co.us/cwcbsearch/0/edoc/227433/CommerceCity_XericDemo_Application.pdf',
   'Katoptron evidence review, 2026-10-20', now(),
   'Colorado Water Conservation Board identifies Commerce City staff email at c3gov.com; the city website explicitly links commerce.legistar.com. Not the City of Commerce, California.'),
  ('slco.org', 'Salt Lake County, UT', 'slco', null, true, 'verified',
   'https://www.utah.gov/pmn/sitemap/notice/927150.html',
   'Katoptron evidence review, 2026-10-20', now(),
   'Utah state public notice identifies the Salt Lake County government domain and slco.legistar.com as its historical agenda portal.')
on conflict (domain) do nothing;

-- Approve additional custom domains ONLY by manually inserting/updating a row
-- after reviewing independent government evidence, jurisdiction identity, and
-- the matching Legistar tenant. Never use a search-result snippet as proof.
