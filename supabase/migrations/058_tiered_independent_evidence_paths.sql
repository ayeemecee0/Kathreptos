-- 058: Evidence tiers. Independently corroborated claims never enter the canonical
-- government-verified camera table or contribute to its statistics.
-- Sources are evaluated by *independence and provenance*, not one required URL shape.
create table public.flock_point_evidence_cases (
  case_key text primary key check(case_key ~ '^tier_[a-z0-9_-]{8,100}$'),
  label text not null check(length(label) between 5 and 140),
  jurisdiction_label text not null check(length(jurisdiction_label) between 4 and 150),
  latitude double precision not null check(latitude between 17 and 72),
  longitude double precision not null check(longitude between -180 and -64),
  evidence_summary text not null check(length(evidence_summary) between 20 and 1500),
  source_url text not null check(source_url ~ '^https://[A-Za-z0-9.-]+/' and length(source_url)<=1600),
  classification text not null default 'candidate'
    check(classification in ('candidate','government_verified','independently_corroborated','rejected','withdrawn')),
  reviewed_at timestamptz,
  review_explanation text,
  staged_at timestamptz not null default now(),
  check(classification not in ('government_verified','independently_corroborated') or
        (reviewed_at is not null and length(btrim(review_explanation))>=60))
);
create index flock_point_cases_latlon_idx on public.flock_point_evidence_cases(latitude,longitude);
create table public.flock_point_evidence_attestations (
  evidence_key text primary key check(evidence_key ~ '^proof_[a-z0-9_-]{8,100}$'),
  case_key text not null references public.flock_point_evidence_cases(case_key),
  source_kind text not null check(source_kind in (
    'government_operated_gis','government_arcgis_organization',
    'original_government_document','independent_field_photo',
    'independent_firsthand_reporting','community_report',
    'third_party_gis','osm_node')),
  source_family text not null check(source_family ~ '^[a-z0-9_.:-]{5,120}$'),
  source_url text not null check(source_url ~ '^https://[A-Za-z0-9.-]+/' and length(source_url)<=1600),
  authority_url text check(authority_url is null or
    (authority_url ~ '^https://[A-Za-z0-9.-]+/' and length(authority_url)<=1600)),
  latitude double precision not null check(latitude between 17 and 72),
  longitude double precision not null check(longitude between -180 and -64),
  evidence_sha256 text not null check(evidence_sha256 ~ '^[a-f0-9]{64}$'),
  source_excerpt text not null check(length(source_excerpt) between 10 and 900),
  evidence_status text not null default 'staged'
    check(evidence_status in ('staged','reviewed','rejected','withdrawn')),
  reviewed_at timestamptz,
  review_explanation text,
  last_checked_at timestamptz not null default now(),
  check(evidence_status <> 'reviewed' or
    (reviewed_at is not null and length(btrim(review_explanation))>=60)),
  check(evidence_status <> 'reviewed' or
    source_kind not in ('government_arcgis_organization','original_government_document',
                       'government_operated_gis') or authority_url is not null),
  unique(case_key,source_family,source_url)
);
create index flock_point_attestations_case_idx
 on public.flock_point_evidence_attestations(case_key,evidence_status,source_family);
create index flock_point_attestations_checked_idx
 on public.flock_point_evidence_attestations(last_checked_at desc);

alter table public.flock_point_evidence_cases enable row level security;
alter table public.flock_point_evidence_attestations enable row level security;
revoke all on public.flock_point_evidence_cases from public,anon,authenticated,service_role;
revoke all on public.flock_point_evidence_attestations from public,anon,authenticated,service_role;

-- A workflow may STAGE evidence without controlling the two approval states.
-- Its restricted INSERT columns exclude classification, evidence_status and
-- all review timestamps/reasons. No workflow UPDATE or DELETE privileges.
grant select on public.flock_point_evidence_cases to service_role;
grant select on public.flock_point_evidence_attestations to service_role;
grant insert(case_key,label,jurisdiction_label,latitude,longitude,evidence_summary,source_url)
 on public.flock_point_evidence_cases to service_role;
grant insert(evidence_key,case_key,source_kind,source_family,source_url,
             authority_url,latitude,longitude,evidence_sha256,source_excerpt)
 on public.flock_point_evidence_attestations to service_role;

-- A private narrowly scoped predicate avoids exposing unpublished evidence
-- through PostgreSQL's public Data API. No dynamic SQL, no user identifiers.
create schema if not exists katoptron_internal;
revoke all on schema katoptron_internal from public;
grant usage on schema katoptron_internal to anon,authenticated;
create function katoptron_internal.point_case_public(p_case_key text)
returns boolean language sql stable security definer set search_path=''
as $tiered_visibility$
  select exists(
    select 1 from public.flock_point_evidence_cases c
    where c.case_key=p_case_key
      and c.classification in ('government_verified','independently_corroborated')
      and c.reviewed_at is not null and length(btrim(c.review_explanation))>=60
      -- Never show an extra provisional copy of an existing original
      -- government verified point from the same jurisdiction.
      and not exists (
        select 1 from public.flock_camera_locations official
        where official.jurisdiction_label=c.jurisdiction_label
          and official.verification_status='verified'
          and abs(official.latitude-c.latitude)<=0.00055
          and abs(official.longitude-c.longitude)*cos(radians(c.latitude))<=0.00055
      )
      and (
        (c.classification='government_verified' and exists(
          select 1 from public.flock_point_evidence_attestations e
          where e.case_key=c.case_key
            and e.evidence_status='reviewed'
            and e.source_kind in ('government_operated_gis','government_arcgis_organization',
                                  'original_government_document')
            and e.authority_url is not null
            and e.reviewed_at is not null and length(btrim(e.review_explanation))>=60
            and e.last_checked_at >= now()-interval '365 days'
            and abs(e.latitude-c.latitude)<=0.00045
            and abs(e.longitude-c.longitude)*cos(radians(c.latitude))<=0.00045
        ))
        or
        (c.classification='independently_corroborated' and (
          select count(distinct e.source_family) >= 2
             and coalesce(bool_or(e.source_kind in (
                'independent_field_photo','independent_firsthand_reporting',
                'government_operated_gis','government_arcgis_organization',
                'original_government_document')),false)
          from public.flock_point_evidence_attestations e
          where e.case_key=c.case_key and e.evidence_status='reviewed'
            and e.reviewed_at is not null and length(btrim(e.review_explanation))>=60
            and e.last_checked_at >= now()-interval '180 days'
            and abs(e.latitude-c.latitude)<=0.00045
            and abs(e.longitude-c.longitude)*cos(radians(c.latitude))<=0.00045
        ))
      )
  );
$tiered_visibility$;
revoke all on function katoptron_internal.point_case_public(text)
 from public,anon,authenticated,service_role;
grant execute on function katoptron_internal.point_case_public(text)
 to anon,authenticated;

create policy published_tiered_claims_only
 on public.flock_point_evidence_cases for select to anon,authenticated
 using (katoptron_internal.point_case_public(case_key));

-- Only safe public columns can be selected, even for an approved claim.
grant select(case_key,label,jurisdiction_label,latitude,longitude,
 classification,evidence_summary,source_url,reviewed_at)
 on public.flock_point_evidence_cases to anon,authenticated;

create view public.flock_public_tiered_camera_points
with (security_invoker=true) as
select c.case_key,c.label,c.jurisdiction_label,c.latitude,c.longitude,
       c.classification as evidence_tier,c.evidence_summary,c.source_url,
       c.reviewed_at as published_at
from public.flock_point_evidence_cases c
where c.classification in ('government_verified','independently_corroborated');
revoke all on public.flock_public_tiered_camera_points
 from public,anon,authenticated,service_role;
grant select on public.flock_public_tiered_camera_points to anon,authenticated;

-- Do not change flock_camera_locations, its RLS, existing 275 records, or
-- source authority promotion RPCs. Existing stats remain officially verified.
