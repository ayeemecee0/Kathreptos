-- 069: A reporter's consent to PRIVATE review never implies consent to public citation.
alter table public.flock_community_submissions
 add column publication_consent boolean not null default false;
grant insert(publication_consent) on public.flock_community_submissions to authenticated;
grant select(publication_consent) on public.flock_community_submissions to authenticated;
-- Continue applying all original evidence source checks, plus explicit
-- public consent and reviewed incorporation for reporter-derived case keys.
create or replace function katoptron_internal.point_case_public(p_case_key text)
returns boolean language sql stable security definer set search_path=''
as $tiered_visibility$
  select exists(
    select 1 from public.flock_point_evidence_cases c
    where c.case_key=p_case_key
      and not exists (
        select 1 from public.flock_community_submissions submitted
        where c.case_key='tier_'||md5(submitted.submission_id::text)
          and (not submitted.publication_consent or submitted.report_status<>'incorporated')
      )
      and c.classification in ('government_verified','independently_corroborated')
      and c.reviewed_at is not null and length(btrim(c.review_explanation))>=60
      -- Never show an extra provisional copy of an existing original
      -- government verified point from the same jurisdiction.
      and not exists (
        select 1 from public.flock_camera_locations official
        where official.verification_status='verified'
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
            and katoptron_internal.tiered_source_current(e.evidence_key)
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
            and katoptron_internal.tiered_source_current(e.evidence_key)
            and abs(e.latitude-c.latitude)<=0.00045
            and abs(e.longitude-c.longitude)*cos(radians(c.latitude))<=0.00045
        ))
      )
  );
$tiered_visibility$;
