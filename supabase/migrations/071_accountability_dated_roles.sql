-- 071: Professional roles are dated, source-attributed assertions, never votes.
-- Public officials must have actual primary government proof, not inferred positions.
create table public.flock_accountability_roles (
 role_key text primary key check(role_key ~ '^[a-z0-9_-]{8,96}$'),
 person_name text not null check(length(person_name) between 5 and 120),
 role_title text not null check(length(role_title) between 4 and 150),
 organization_name text not null check(length(organization_name) between 4 and 150),
 role_category text not null check(role_category in ('flock_vendor_leadership','government_official')),
 source_publisher text not null check(length(source_publisher) between 4 and 160),
 source_type text not null check(source_type in ('official_vendor_announcement','original_government_record')),
 source_url text not null check(source_url ~ '^https://[A-Za-z0-9.-]+/' and length(source_url)<1500),
 source_date date not null check(source_date>=date '2000-01-01' and source_date<=current_date),
 evidence_description text not null check(length(evidence_description) between 35 and 600),
 review_status text not null default 'candidate'
   check(review_status in ('candidate','verified','withdrawn')),
 reviewed_at timestamptz,
 last_checked_at timestamptz,
 check(review_status<>'verified' or (reviewed_at is not null and last_checked_at is not null)),
 check((role_category='flock_vendor_leadership' and source_type='official_vendor_announcement')
    or (role_category='government_official' and source_type='original_government_record'))
);
alter table public.flock_accountability_roles enable row level security;
revoke all on public.flock_accountability_roles from public,anon,authenticated,service_role;
grant select(role_key,person_name,role_title,organization_name,role_category,source_publisher,source_type,source_url,source_date,evidence_description,reviewed_at,last_checked_at)
 on public.flock_accountability_roles to anon,authenticated;
create policy published_roles_with_dated_primary_sources
on public.flock_accountability_roles for select to anon,authenticated
using(review_status='verified' and source_url like 'https://%'
 and reviewed_at is not null and last_checked_at is not null);
-- Roles are cited professional identities only. Never publish personal details.
insert into public.flock_accountability_roles(
role_key,person_name,role_title,organization_name,role_category,source_publisher,source_type,
source_url,source_date,evidence_description,review_status,reviewed_at,last_checked_at) values
('flock_garrett_langley_ceo','Garrett Langley','Founder and Chief Executive Officer','Flock Safety',
'flock_vendor_leadership','Flock Safety','official_vendor_announcement',
'https://www.flocksafety.com/blog/flock-safety-ceo-garrett-langley-ted2026',date '2026-07-21',
'Flock Safety publicly identifies Garrett Langley as founder and CEO in its July 2026 article. This establishes a company-reported professional role, not a government action.',
'verified',now(),now()),
('flock_chris_castaldo_ciso','Chris Castaldo','Chief Information Security Officer','Flock Safety',
'flock_vendor_leadership','Flock Safety','official_vendor_announcement',
'https://www.flocksafety.com/blog/flock-safety-appoints-chris-castaldo-as-chief-information-security-officer',
date '2025-12-08',
'Flock Safety announced the appointment of Chris Castaldo as CISO in December 2025. The source establishes an appointment as of its publication, not continuous employment verification.',
'verified',now(),now()),
('flock_matthew_webster_cmo','Matthew Webster','Chief Marketing Officer','Flock Safety',
'flock_vendor_leadership','Flock Safety','official_vendor_announcement',
'https://www.flocksafety.com/blog/flock-safety-appoints-matthew-webster-as-cmo',
date '2025-09-16',
'Flock Safety announced the appointment of Matthew Webster as CMO in September 2025. The dated official appointment does not independently confirm his employment today.',
'verified',now(),now());
