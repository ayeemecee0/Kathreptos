-- 059: Connect independently obtained private leads and live trusted GIS receipts
-- to tiered evidence without permitting a crawler to self-authorize publication.
alter table public.flock_point_evidence_attestations
 add column official_camera_record_key text
 references public.flock_camera_locations(record_key);

create index tiered_attestations_official_fk_idx
 on public.flock_point_evidence_attestations(official_camera_record_key)
 where official_camera_record_key is not null;

-- The original-government-derived attestation is only "current" while its
-- actual official camera, trusted source and independently authorized GIS
-- endpoint all remain verified. Other evidence requires separate owner review.
create function katoptron_internal.tiered_source_current(p_evidence_key text)
returns boolean language sql stable security definer set search_path=''
as $tier_source_current$
 select exists (
   select 1 from public.flock_point_evidence_attestations e
   where e.evidence_key=p_evidence_key
     and (e.official_camera_record_key is null or exists (
       select 1 from public.flock_camera_locations v
       join public.trusted_flock_gis_sources s on s.gis_layer_url=v.source_url
       where v.record_key=e.official_camera_record_key
         and v.verification_status='verified'
         and v.location_accuracy='exact'
         and v.verification_method='official_georeferenced_camera_record_v1'
         and s.source_status='verified'
         and s.jurisdiction_label=v.jurisdiction_label
         and e.source_url=v.source_url
         and e.evidence_sha256=v.evidence_sha256
         and public.gis_camera_authority_current(v.source_url,v.jurisdiction_label)
     ))
 );
$tier_source_current$;
revoke all on function katoptron_internal.tiered_source_current(text)
 from public,anon,authenticated,service_role;
grant execute on function katoptron_internal.tiered_source_current(text)
 to anon,authenticated,service_role;

-- Enforce live authority in BOTH government and independent source tiers;
-- deduplicate nearby canonical cameras across jurisdiction-label differences.
create or replace function katoptron_internal.point_case_public(p_case_key text)
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
-- RPC usable by the workflow has no arbitrary input URL, review flags,
-- coordinates, source key or case status. It only reads existing private
-- candidate rows and DB-confirmed matches to existing official sources.
create function public.stage_tiered_evidence_from_verified_matches(p_limit int default 250)
returns jsonb language plpgsql security definer set search_path=''
as $tier_stage$
declare
  c record;
  m record;
  inserted_cases int:=0;
  inserted_osm int:=0;
  inserted_gov int:=0;
  n int;
  key text;
  maxrows int;
begin
  maxrows:=least(greatest(coalesce(p_limit,250),1),600);
  for c in
    select src.* from public.flock_camera_discovery_candidates src
    where src.source_kind='osm_public_dataset'
      and src.candidate_status='unverified'
      and src.declared_vendor='Flock Safety'
      and src.evidence_fingerprint ~ '^[a-f0-9]{64}$'
      and src.source_url ~ '^https://www[.]openstreetmap[.]org/node/[0-9]+$'
      and length(src.evidence_excerpt) between 10 and 900
      and not exists(
        select 1 from public.flock_point_evidence_cases t
        where t.case_key='tier_'||md5(src.candidate_key)
      )
    order by src.candidate_key limit maxrows
  loop
    key:='tier_'||md5(c.candidate_key);
    insert into public.flock_point_evidence_cases
      (case_key,label,jurisdiction_label,latitude,longitude,evidence_summary,source_url)
    values(key,'Possible Flock camera - OSM candidate','Jurisdiction not yet authenticated',
      c.latitude,c.longitude,
      'OpenStreetMap community vendor label identifies a possible Flock device. Camera identity, placement and operation remain unverified.',
      c.source_url)
    on conflict(case_key) do nothing;
    get diagnostics n=row_count;
    inserted_cases:=inserted_cases+n;
    insert into public.flock_point_evidence_attestations
      (evidence_key,case_key,source_kind,source_family,source_url,
       latitude,longitude,evidence_sha256,source_excerpt,last_checked_at)
    values ('proof_'||md5('osm:'||c.candidate_key),key,'osm_node',
      'openstreetmap',c.source_url,c.latitude,c.longitude,
      c.evidence_fingerprint,c.evidence_excerpt,least(c.last_seen_at,now()))
    on conflict(evidence_key) do nothing;
    get diagnostics n=row_count;
    inserted_osm:=inserted_osm+n;
  end loop;

  -- These associations are VERIFIED TWICE: by the original independent
  -- match trigger and here against current owner-trusted government GIS.
  -- Revoke/recheck changes are evaluated again at *public read* time.
  for m in
    select distinct on (v.record_key, c.candidate_key)
      c.candidate_key,c.latitude,c.longitude,c.source_url as osm_url,
      v.record_key,v.source_url as official_url,v.jurisdiction_label,
      v.latitude as official_lat,v.longitude as official_lon,
      v.evidence_sha256,v.evidence_summary,v.last_source_recheck_at,
      s.source_key,s.government_evidence_url
    from public.flock_camera_source_matches match
    join public.flock_camera_discovery_candidates c
      on c.candidate_key=match.candidate_key
    join public.flock_camera_locations v
      on v.record_key=match.verified_camera_key
    join public.trusted_flock_gis_sources s
      on s.gis_layer_url=v.source_url
     and s.jurisdiction_label=v.jurisdiction_label
     and s.source_status='verified'
    where match.matching_method='trusted_gis_to_osm_30m_v1'
      and match.distance_m <= 30
      and c.source_kind='osm_public_dataset'
      and c.candidate_status='unverified'
      and v.source_type='official_government'
      and v.verification_status='verified'
      and v.location_accuracy='exact'
      and v.verification_method='official_georeferenced_camera_record_v1'
      and v.last_source_recheck_at <= now()
      and v.last_source_recheck_at > now()-interval '30 days'
      and length(v.evidence_summary)>=10
      and public.gis_camera_authority_current(v.source_url,v.jurisdiction_label)
      and exists(
        select 1 from public.flock_point_evidence_cases t
        where t.case_key='tier_'||md5(c.candidate_key)
      )
    order by v.record_key,c.candidate_key
    limit maxrows
  loop
    key:='tier_'||md5(m.candidate_key);
    -- A government-verified label is derived only from its authenticated
    -- inventory record. This is not approval of the OSM claim.
    update public.flock_point_evidence_cases
      set jurisdiction_label=m.jurisdiction_label
    where case_key=key and classification='candidate'
      and reviewed_at is null and jurisdiction_label='Jurisdiction not yet authenticated';
    insert into public.flock_point_evidence_attestations
      (evidence_key,case_key,source_kind,source_family,source_url,
       authority_url,latitude,longitude,evidence_sha256,source_excerpt,
       evidence_status,reviewed_at,review_explanation,last_checked_at,
       official_camera_record_key)
    values (
       'proof_'||md5('official:'||m.record_key||':'||m.candidate_key),
       key,'government_operated_gis','official-gis.'||m.source_key,
       m.official_url,m.government_evidence_url,m.official_lat,m.official_lon,
       m.evidence_sha256,left(m.evidence_summary,900),
       'reviewed',now(),
       'Auto-attested from a live, previously owner-approved government GIS point and immutable independent community-to-government match; community vendor tag is not approved.',
       m.last_source_recheck_at,m.record_key)
    on conflict(evidence_key) do update
      set evidence_sha256=excluded.evidence_sha256,
          last_checked_at=excluded.last_checked_at,
          source_excerpt=excluded.source_excerpt,
          reviewed_at=now(),
          review_explanation=excluded.review_explanation
      where public.flock_point_evidence_attestations.official_camera_record_key=
              excluded.official_camera_record_key
        and public.flock_point_evidence_attestations.case_key=excluded.case_key
        and public.flock_point_evidence_attestations.source_url=excluded.source_url
        and public.flock_point_evidence_attestations.evidence_status='reviewed';
    get diagnostics n=row_count;
    inserted_gov:=inserted_gov+n;
  end loop;
  return jsonb_build_object('staged_cases',inserted_cases,
     'staged_osm_attestations',inserted_osm,
     'reverified_government_attestations',inserted_gov);
end;
$tier_stage$;
revoke all on function public.stage_tiered_evidence_from_verified_matches(int)
 from public,anon,authenticated,service_role;
grant execute on function public.stage_tiered_evidence_from_verified_matches(int) to service_role;

-- A separate reconciliation pass may change "candidate" to a published tier
-- ONLY when *previously reviewed attestations* satisfy live independent
-- evidence checks. No input from the caller affects trust or evidence state.
create function public.reconcile_tiered_evidence_cases(p_limit int default 150)
returns jsonb language plpgsql security definer set search_path=''
as $tier_reconcile$
declare
  rec record;
  gov_ok boolean;
  dual_ok boolean;
  published_gov int:=0;
  published_corroborated int:=0;
begin
  for rec in select * from public.flock_point_evidence_cases c
    where c.classification='candidate'
      and not exists (
        select 1 from public.flock_camera_locations o
        where o.verification_status='verified'
          and abs(o.latitude-c.latitude)<=0.00055
          and abs(o.longitude-c.longitude)*cos(radians(c.latitude))<=0.00055
      )
    order by c.staged_at,c.case_key limit least(greatest(coalesce(p_limit,150),1),600)
  loop
    select exists (
      select 1 from public.flock_point_evidence_attestations e
      where e.case_key=rec.case_key
        and e.evidence_status='reviewed'
        and e.source_kind in ('government_operated_gis',
           'government_arcgis_organization','original_government_document')
        and e.authority_url is not null
        and e.reviewed_at is not null
        and length(btrim(e.review_explanation))>=60
        and e.last_checked_at>=now()-interval '365 days'
        and abs(e.latitude-rec.latitude)<=0.00045
        and abs(e.longitude-rec.longitude)*cos(radians(rec.latitude))<=0.00045
        and katoptron_internal.tiered_source_current(e.evidence_key)
    ) into gov_ok;
    if gov_ok then
      update public.flock_point_evidence_cases
        set classification='government_verified',reviewed_at=now(),
          review_explanation='Automatically published from independently reviewed government-origin georeferenced evidence. The automated reconciler cannot review or fabricate evidence.'
      where case_key=rec.case_key and classification='candidate';
      published_gov:=published_gov+1;
      continue;
    end if;
    select count(distinct e.source_family)>=2
       and coalesce(bool_or(e.source_kind in (
         'government_operated_gis','government_arcgis_organization',
         'original_government_document','independent_field_photo',
         'independent_firsthand_reporting')),false)
    into dual_ok
    from public.flock_point_evidence_attestations e
    where e.case_key=rec.case_key
      and e.evidence_status='reviewed'
      and e.reviewed_at is not null
      and length(btrim(e.review_explanation))>=60
      and e.last_checked_at>=now()-interval '180 days'
      and abs(e.latitude-rec.latitude)<=0.00045
      and abs(e.longitude-rec.longitude)*cos(radians(rec.latitude))<=0.00045
      and katoptron_internal.tiered_source_current(e.evidence_key);
    if coalesce(dual_ok,false) then
      update public.flock_point_evidence_cases
        set classification='independently_corroborated',reviewed_at=now(),
        review_explanation='Automatically classified using two separately reviewed independent provenance families with agreeing source coordinates. No automated source was granted approval privileges.'
      where case_key=rec.case_key and classification='candidate';
      published_corroborated:=published_corroborated+1;
    end if;
  end loop;
  return jsonb_build_object('government_qualified',published_gov,
    'corroborated_qualified',published_corroborated);
end;
$tier_reconcile$;
revoke all on function public.reconcile_tiered_evidence_cases(int)
 from public,anon,authenticated,service_role;
grant execute on function public.reconcile_tiered_evidence_cases(int) to service_role;
