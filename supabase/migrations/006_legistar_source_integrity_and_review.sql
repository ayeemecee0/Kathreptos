-- Stage and preserve original Legistar evidence before any publication.
--
-- IMPORTANT: the WebAPI MatterId is not generally the public LegislationDetail
-- page ID. Earlier generated URLs may point to another matter or be invalid.
-- The canonical official API endpoint is deterministic, but only a direct,
-- independently matched public page can become official_page_url.
--
-- This private evidence-review layer MUST NOT automatically publish records.

create table if not exists public.agenda_evidence_reviews (
  discovery_queue_id uuid primary key references public.discovery_queue(id) on delete cascade,
  tenant text not null check (tenant ~ '^[a-z0-9-]{3,40}$'),
  matter_id bigint not null check (matter_id > 0),
  official_api_url text not null unique
    check (official_api_url ~ '^https://webapi\.legistar\.com/v1/[a-z0-9-]{3,40}/matters/[0-9]+$'),
  original_discovery_url text not null check (original_discovery_url ~ '^https://'),
  official_page_url text check (official_page_url is null or official_page_url ~ '^https://'),
  reviewed_primary_source_url text check (reviewed_primary_source_url is null or reviewed_primary_source_url ~ '^https://'),
  suggested_topic text not null default 'unclassified'
    check (suggested_topic in ('unclassified','contract_or_procurement','presentation','policy_or_oversight')),
  suspected_flock_reference text not null default 'unconfirmed'
    check (suspected_flock_reference in ('unconfirmed','mentioned_in_metadata','not_mentioned_in_metadata')),
  verified_vendor_relation text not null default 'not_assessed'
    check (verified_vendor_relation in ('not_assessed','explicit_flock','different_vendor','general_alpr','indeterminate')),
  decision_outcome text not null default 'not_assessed'
    check (decision_outcome in ('not_assessed','proposed','approved','failed','heard','informational','other')),
  review_state text not null default 'needs_primary_review'
    check (review_state in ('needs_primary_review','source_verified','ready_to_publish','published','rejected')),
  reviewed_claim text,
  reviewer_notes text,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(tenant,matter_id),
  check (review_state = 'needs_primary_review' or review_state = 'rejected'
         or (reviewed_primary_source_url is not null and reviewed_by is not null
             and reviewed_at is not null and nullif(trim(reviewed_claim), '') is not null))
);

create index if not exists agenda_evidence_reviews_status_idx
  on public.agenda_evidence_reviews (review_state, suggested_topic);

alter table public.agenda_evidence_reviews enable row level security;
revoke all on public.agenda_evidence_reviews from anon, authenticated;

-- Initial triage is based solely on already-queued API metadata and is NOT
-- independent source verification. No review_state is advanced here.
insert into public.agenda_evidence_reviews (
  discovery_queue_id, tenant, matter_id, official_api_url, original_discovery_url,
  suggested_topic, suspected_flock_reference)
select q.id,
       m.groups[1],
       m.groups[2]::bigint,
       'https://webapi.legistar.com/v1/' || m.groups[1] || '/matters/' || m.groups[2],
       q.url,
       case
         when lower(q.headline || ' ' || coalesce(q.snippet,'')) ~ '(contract|agreement|lease|procurement)' then 'contract_or_procurement'
         when lower(q.headline || ' ' || coalesce(q.snippet,'')) ~ '(presentation|safe cities program)' then 'presentation'
         when lower(q.headline || ' ' || coalesce(q.snippet,'')) ~ '(policy|legislation|resolution|ordinance|data sharing|report)' then 'policy_or_oversight'
         else 'unclassified' end,
       case when lower(q.headline || ' ' || coalesce(q.snippet,'')) ~ '(flock[[:space:]]+safety|flock[[:space:]]+agreement|flock[[:space:]]+contract|flock[[:space:]]+user)'
         then 'mentioned_in_metadata' else 'not_mentioned_in_metadata' end
from public.discovery_queue q
cross join lateral (
  select regexp_match(q.url,
    '^https://([a-z0-9-]+)\.legistar\.com/LegislationDetail\.aspx\?ID=([0-9]+)$') as groups
) m
where m.groups is not null
on conflict do nothing;

-- Retain the incorrect historical URL in agenda_evidence_reviews; replace
-- only its corresponding queue URL with the verifiable official API endpoint.
update public.discovery_queue q
set url = r.official_api_url
from public.agenda_evidence_reviews r
where r.discovery_queue_id = q.id
  and q.url = r.original_discovery_url
  and q.url <> r.official_api_url;

-- Subsequent discoveries automatically receive a PRIVATE triage record,
-- never a public source approval. The discovery_queue has no anonymous write.
create or replace function public.stage_legistar_matter_review()
returns trigger
language plpgsql
set search_path = pg_catalog
as $stage_legistar_matter_review$
declare
  m text[];
begin
  m := regexp_match(new.url,
    '^https://webapi\.legistar\.com/v1/([a-z0-9-]{3,40})/matters/([0-9]+)$');
  if m is not null then
    insert into public.agenda_evidence_reviews (
      discovery_queue_id, tenant, matter_id, official_api_url, original_discovery_url,
      suggested_topic, suspected_flock_reference)
    values (
      new.id, m[1], m[2]::bigint, new.url, new.url,
      case
        when lower(new.headline || ' ' || coalesce(new.snippet,'')) ~ '(contract|agreement|lease|procurement)' then 'contract_or_procurement'
        when lower(new.headline || ' ' || coalesce(new.snippet,'')) ~ '(presentation|safe cities program)' then 'presentation'
        when lower(new.headline || ' ' || coalesce(new.snippet,'')) ~ '(policy|legislation|resolution|ordinance|data sharing|report)' then 'policy_or_oversight'
        else 'unclassified' end,
      case when lower(new.headline || ' ' || coalesce(new.snippet,'')) ~ '(flock[[:space:]]+safety|flock[[:space:]]+agreement|flock[[:space:]]+contract|flock[[:space:]]+user)'
        then 'mentioned_in_metadata' else 'not_mentioned_in_metadata' end)
    on conflict do nothing;
  end if;
  return new;
end;
$stage_legistar_matter_review$;

drop trigger if exists stage_legistar_review_on_queue_insert
  on public.discovery_queue;
create trigger stage_legistar_review_on_queue_insert
after insert on public.discovery_queue
for each row execute function public.stage_legistar_matter_review();
