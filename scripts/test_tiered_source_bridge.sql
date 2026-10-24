-- Transactional end-to-end test: no artificial candidate persists after ROLLBACK.
begin;
insert into public.flock_camera_discovery_candidates
(candidate_key,source_kind,source_url,source_external_id,latitude,longitude,
 declared_vendor,evidence_excerpt,evidence_fingerprint)
values('osm:node:999999998','osm_public_dataset',
'https://www.openstreetmap.org/node/999999998','999999998',
35.101,-106.601,'Flock Safety',
'Community map label identifies a possible Flock camera but does not confirm presence or operation.',
repeat('a',64));

set role service_role;
select public.stage_tiered_evidence_from_verified_matches(10);
select public.reconcile_tiered_evidence_cases(10);
reset role;
do $tier_test$
begin
 if (select count(*) from public.flock_point_evidence_cases
   where case_key='tier_'||md5('osm:node:999999998') and classification='candidate')<>1
  then raise exception 'OSM candidate did not stage without promoting';end if;
 if (select count(*) from public.flock_point_evidence_attestations
   where case_key='tier_'||md5('osm:node:999999998')
     and source_family='openstreetmap' and evidence_status='staged')<>1
  then raise exception 'OSM attestation was not staged privately';end if;
end $tier_test$;

set role anon;
do $tier_test$
begin
 if (select count(*) from public.flock_public_tiered_camera_points
    where case_key='tier_'||md5('osm:node:999999998'))<>0
  then raise exception 'Unreviewed discovery exposed camera';end if;
 if has_function_privilege('anon','public.stage_tiered_evidence_from_verified_matches(integer)','EXECUTE')
   or has_function_privilege('anon','public.reconcile_tiered_evidence_cases(integer)','EXECUTE')
  then raise exception 'Public caller can invoke service-only evidence RPC';end if;
end $tier_test$;
reset role;

-- Attacker possessing service-role discovery credentials cannot set approval.
set role service_role;
do $tier_test$
begin
 if has_table_privilege('service_role','public.flock_point_evidence_attestations','UPDATE')
  or has_table_privilege('service_role','public.flock_point_evidence_cases','UPDATE')
  then raise exception 'Discovery key can grant its own review';end if;
end $tier_test$;
reset role;

-- Owner-reviewed independent upstream sources unlock ONLY the provisional tier.
-- Automation itself does not create these review credentials or attestations.
update public.flock_point_evidence_attestations set
 evidence_status='reviewed',reviewed_at=now(),
 review_explanation='Independent owner validation confirmed the origin and coordinates of this fictional source during a transactional database test.'
where evidence_key='proof_'||md5('osm:osm:node:999999998');
insert into public.flock_point_evidence_attestations
 (evidence_key,case_key,source_kind,source_family,source_url,
 latitude,longitude,evidence_sha256,source_excerpt,
 evidence_status,reviewed_at,review_explanation)
values(
 'proof_'||md5('field:999999998'),
 'tier_'||md5('osm:node:999999998'),
 'independent_field_photo','field-original-example.test',
 'https://example.org/field/photo/999999998',
 35.10101,-106.60101,repeat('b',64),
 'Independent first-hand dated photograph with documented precise coordinates.',
 'reviewed',now(),
 'Independent owner validation of a source-specific, original first-hand photo without relying on the OSM community map dataset.');
set role service_role;
select public.reconcile_tiered_evidence_cases(40);
reset role;

set role anon;
do $tier_test$
begin
 if (select count(*) from public.flock_public_tiered_camera_points
    where case_key='tier_'||md5('osm:node:999999998')
      and evidence_tier='independently_corroborated')<>1
  then raise exception 'Reviewed independent sources did not activate provisional status';end if;
end $tier_test$;
reset role;

-- Withdraw a necessary independent source; public eligibility must fail open
-- to no pin even while the prior classification remains recorded historically.
update public.flock_point_evidence_attestations
 set evidence_status='withdrawn'
where evidence_key='proof_'||md5('field:999999998');
set role anon;
do $tier_test$
begin
 if (select count(*) from public.flock_public_tiered_camera_points
    where case_key='tier_'||md5('osm:node:999999998'))<>0
  then raise exception 'Withdrawn field evidence remained published';end if;
end $tier_test$;
reset role;
rollback;
