-- Milestone 5: multi-actor regression; every record is rolled back.
-- Execute as database owner on disposable CI PostgreSQL or in a single
-- production transaction. Never persist these synthetic users or cases.
begin;
select set_config('katoptron.test_contributor_a',gen_random_uuid()::text,true);
select set_config('katoptron.test_contributor_b',gen_random_uuid()::text,true);
select set_config('katoptron.test_reviewer',gen_random_uuid()::text,true);
insert into auth.users(id)
values(current_setting('katoptron.test_contributor_a')::uuid),
      (current_setting('katoptron.test_contributor_b')::uuid),
      (current_setting('katoptron.test_reviewer')::uuid);
insert into public.editorial_reviewers(user_id,role,granted_by)
values(current_setting('katoptron.test_reviewer')::uuid,'publisher','rollback-only integration test');
select set_config('request.jwt.claim.sub',current_setting('katoptron.test_contributor_a'),true);
set local role authenticated;
with created as (
 insert into public.flock_community_submissions
 (latitude,longitude,description,original_source_url,consent_to_review,publication_consent)
 values (38.5741,-121.4831,
 'Rollback-only synthetic contributor A report. This does not depict an actual camera and must never appear on a public map.',
 'https://example.org/katoptron-qa-a',true,false)
 returning submission_id
) select set_config('katoptron.test_case_a',submission_id::text,true) from created;
do $qa$
begin
 if (select count(*) from public.flock_community_submissions
   where submission_id=current_setting('katoptron.test_case_a')::uuid)<>1
 then raise exception 'Contributor A cannot read own receipt';end if;
 if has_table_privilege('authenticated','public.flock_community_screening','SELECT')
 then raise exception 'Private screening directly exposed to contributors';end if;
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.test_contributor_b'),true);
do $qa$
begin
 if exists(select 1 from public.flock_community_submissions
   where submission_id=current_setting('katoptron.test_case_a')::uuid)
 then raise exception 'Contributor B can read contributor A report';end if;
 if public.withdraw_own_community_report(current_setting('katoptron.test_case_a')::uuid)
 then raise exception 'Contributor B withdrew contributor A report';end if;
 begin
  perform public.list_community_review_queue(5);
  raise exception 'Contributor B bypassed reviewer queue';
 exception when insufficient_privilege then null;
 end;
 if to_regprocedure('public.community_report_attachment_paths(uuid)') is not null then
  begin
   perform public.community_report_attachment_paths(current_setting('katoptron.test_case_a')::uuid);
   raise exception 'Contributor B bypassed private attachment list';
  exception when insufficient_privilege then null;
  end;
 else
  raise notice 'Ephemeral CI has no Supabase Storage schema; attachment RLS tested separately in production';
 end if;
end $qa$;
with created as (
 insert into public.flock_community_submissions
 (latitude,longitude,description,original_source_url,consent_to_review)
 values (38.57412,-121.4831,
 'Rollback-only synthetic contributor B close-by report. Nearby reports are screening leads only, never independent verification.',
 'https://example.org/katoptron-qa-b',true)
 returning submission_id
) select set_config('katoptron.test_case_b',submission_id::text,true) from created;
select set_config('request.jwt.claim.sub',current_setting('katoptron.test_reviewer'),true);
do $qa$
begin
 if not exists(select 1 from public.list_community_review_queue(100)
 where submission_id=current_setting('katoptron.test_case_a')::uuid) then
 raise exception 'Reviewer cannot access queued report A';end if;
 if not exists(select 1 from public.list_community_review_queue(100)
 where submission_id=current_setting('katoptron.test_case_b')::uuid) then
 raise exception 'Reviewer cannot access queued report B';end if;
 perform public.set_community_review_status(
  current_setting('katoptron.test_case_a')::uuid,'incorporated',
  'Synthetic case added only to the private research ledger for the rollback-only test.');
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.test_contributor_a'),true);
do $qa$
begin
 if not public.withdraw_own_community_report(current_setting('katoptron.test_case_a')::uuid)
 then raise exception 'Owner A cannot withdraw own report';end if;
end $qa$;
reset role;
do $qa$
declare a uuid:=current_setting('katoptron.test_case_a')::uuid;
        b uuid:=current_setting('katoptron.test_case_b')::uuid;
begin
 if (select report_status from public.flock_community_submissions where submission_id=a)<>'withdrawn'
 then raise exception 'Withdrawal did not transition status';end if;
 if (select screening_state from public.flock_community_screening where submission_id=b)<>'possible_duplicate'
 then raise exception 'Nearby report not screened as possible duplicate';end if;
 if (select count(*) from public.flock_community_review_history where submission_id=a
   and new_status='incorporated')<>1
 then raise exception 'Review audit trail missing';end if;
 if (select classification from public.flock_point_evidence_cases
   where case_key='tier_'||md5(a::text))<>'withdrawn'
 then raise exception 'Withdrawn case still classified as current';end if;
 if (select evidence_status from public.flock_point_evidence_attestations
   where evidence_key='proof_'||md5(a::text))<>'withdrawn'
 then raise exception 'Withdrawn report source still live';end if;
 if (select katoptron_internal.point_case_public('tier_'||md5(a::text)))
 then raise exception 'Withdrawn community source was published';end if;
 if (select katoptron_internal.point_case_public('tier_'||md5(b::text)))
 then raise exception 'Non-consenting unreviewed source was published';end if;
end $qa$;
rollback;
