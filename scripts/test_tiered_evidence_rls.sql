-- Executed in a transaction in throwaway CI PostgreSQL, never publishes test pins.
begin;
insert into public.flock_point_evidence_cases
(case_key,label,jurisdiction_label,latitude,longitude,evidence_summary,source_url)
values
('tier_8proof_case_test','Potential Flock camera test','Fictional County, NM',
 35.1000,-106.6000,'A fictional test case with isolated first-person corroboration.',
 'https://example.com/source'),
('tier_8proof_gov_test','Official Flock point test','Fictional City, NM',
 35.2000,-106.7000,'A test for independent governmental authority attestation.',
 'https://example.com/gov');

insert into public.flock_point_evidence_attestations
(evidence_key,case_key,source_kind,source_family,source_url,
 latitude,longitude,evidence_sha256,source_excerpt)
values
('proof_alpha000000','tier_8proof_case_test','osm_node',
 'openstreetmap','https://example.com/osm',35.10001,-106.60001,repeat('a',64),
 'Flock-branded roadside pole (unverified)'),
('proof_beta0000000','tier_8proof_case_test','independent_field_photo',
 'independent.photo.001','https://example.com/photo',35.10002,-106.60002,repeat('b',64),
 'Distinct dated field observation of Flock-branded device'),
('proof_gamma000000','tier_8proof_case_test','osm_node',
 'openstreetmap','https://example.com/osm2',35.1000,-106.6000,repeat('c',64),
 'Same underlying OSM provider, must not count independently'),
('proof_gov00000000','tier_8proof_gov_test','government_arcgis_organization',
 'verified.gov.portal.001','https://example.com/arcgis',
 35.20001,-106.70001,repeat('d',64),'Original agency GIS feature with point identity');
update public.flock_point_evidence_attestations set
 evidence_status='reviewed', reviewed_at=now(),
 review_explanation='Independently reviewed source provenance and device identity are supported for this artificial CI fixture.'
where evidence_key in ('proof_alpha000000','proof_gamma000000');
update public.flock_point_evidence_cases set
 classification='independently_corroborated', reviewed_at=now(),
 review_explanation='Artificial test case has a vetted map source, but no independently checked second information source.'
where case_key='tier_8proof_case_test';
update public.flock_point_evidence_cases set
 classification='government_verified', reviewed_at=now(),
 review_explanation='Artificial original-government GIS portal authenticity is separately checked for this exact test feature.'
where case_key='tier_8proof_gov_test';

-- Neither two mirrors from a single upstream source, nor an official
-- attestation missing a government authority URL, may become public.
set role anon;
do $$
begin
 if (select count(*) from public.flock_public_tiered_camera_points) <> 0 then
  raise exception 'Private or uncited cases escaped public filter';
 end if;
end $$;
reset role;

update public.flock_point_evidence_attestations set authority_url='https://example.gov/official-map', evidence_status='reviewed', reviewed_at=now(), review_explanation='Authenticated government ArcGIS organization affiliation confirmed by independent municipal records and source geometry.'
where evidence_key='proof_gov00000000';
set role anon;
do $$
begin
 if (select count(*) from public.flock_public_tiered_camera_points) <> 1 then
   raise exception 'Reviewed authenticated government path did not publish';
 end if;
end $$;
reset role;

update public.flock_point_evidence_attestations set
 evidence_status='reviewed',reviewed_at=now(),
 review_explanation='Directly observed independent dated photo source, independently checked with upstream provenance.'
where evidence_key='proof_beta0000000';
set role anon;
do $$
begin
 if (select count(*) from public.flock_public_tiered_camera_points) <> 2 then
   raise exception 'Two independent vetted sources did not publish provisional case';
 end if;
 if (select count(*) from public.flock_public_tiered_camera_points
       where evidence_tier='independently_corroborated') <> 1 then
   raise exception 'Provisional evidence classification is not distinct';
 end if;
end $$;
reset role;

-- A source can remain "reviewed" but not count if it disagrees on
-- geography or if its most recent evidence check has expired.
update public.flock_point_evidence_attestations set latitude=35.13000
where evidence_key='proof_beta0000000';
set role anon;
do $
begin
 if (select count(*) from public.flock_public_tiered_camera_points) <> 1 then
   raise exception 'Distant corroboration must not qualify a provisional point';
 end if;
end $;
reset role;
update public.flock_point_evidence_attestations
  set latitude=35.10002,last_checked_at=now()-interval '181 days'
where evidence_key='proof_beta0000000';
set role anon;
do $
begin
 if (select count(*) from public.flock_public_tiered_camera_points) <> 1 then
   raise exception 'Stale corroboration must not keep a provisional point public';
 end if;
end $;
reset role;
update public.flock_point_evidence_attestations set last_checked_at=now()
where evidence_key='proof_beta0000000';

update public.flock_point_evidence_attestations set evidence_status='withdrawn'
where evidence_key='proof_beta0000000';
set role anon;
do $$
begin
 if (select count(*) from public.flock_public_tiered_camera_points) <> 1 then
   raise exception 'Withdrawn corroborating evidence did not unpublish immediately';
 end if;
end $$;
reset role;

-- No service-role approval capability, and no public read of private sources.
do $$
begin
 if has_table_privilege('service_role','public.flock_point_evidence_cases','UPDATE')
    or has_table_privilege('service_role','public.flock_point_evidence_attestations','UPDATE')
    or has_table_privilege('anon','public.flock_point_evidence_attestations','SELECT') then
   raise exception 'Source approval or private evidence escaped least privilege';
 end if;
end $$;
rollback;
