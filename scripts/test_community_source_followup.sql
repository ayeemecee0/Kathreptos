-- 079 regression: only a report owner can add a previously missing source once.
begin;
select set_config('katoptron.src_test_owner',gen_random_uuid()::text,true);
select set_config('katoptron.src_test_other',gen_random_uuid()::text,true);
select set_config('katoptron.src_test_reviewer',gen_random_uuid()::text,true);
insert into auth.users(id) values
 (current_setting('katoptron.src_test_owner')::uuid),
 (current_setting('katoptron.src_test_other')::uuid),
 (current_setting('katoptron.src_test_reviewer')::uuid);
insert into public.editorial_reviewers(user_id,role,granted_by) values
 (current_setting('katoptron.src_test_reviewer')::uuid,'publisher','rollback-only-source-followup-qa');
select set_config('request.jwt.claim.sub',current_setting('katoptron.src_test_owner'),true);
set local role authenticated;
with inserted as (
 insert into public.flock_community_submissions(latitude,longitude,description,consent_to_review)
 values(38.59,-121.44,
 'Synthetic research report used to verify safe source followup, not a camera observation.',true)
 returning submission_id
)
select set_config('katoptron.src_case_id',submission_id::text,true) from inserted;
select set_config('request.jwt.claim.sub',current_setting('katoptron.src_test_other'),true);
do $qa$
declare n int;
begin
 update public.flock_community_submissions
 set original_source_url='https://example.org/attacker-substitution'
 where submission_id=current_setting('katoptron.src_case_id')::uuid;
 get diagnostics n=row_count;
 if n<>0 then raise exception 'Other contributor could change private source';end if;
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.src_test_owner'),true);
do $qa$
declare n int;
begin
 update public.flock_community_submissions
 set original_source_url='https://example.org/original-citation'
 where submission_id=current_setting('katoptron.src_case_id')::uuid;
 get diagnostics n=row_count;
 if n<>1 then raise exception 'Owner could not add missing source';end if;
 update public.flock_community_submissions
 set original_source_url='https://example.org/changed-after-review'
 where submission_id=current_setting('katoptron.src_case_id')::uuid;
 get diagnostics n=row_count;
 if n<>0 then raise exception 'Reporter overwrote their already-submitted original';end if;
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.src_test_reviewer'),true);
do $qa$
begin
 perform public.set_community_review_status(
 current_setting('katoptron.src_case_id')::uuid,'incorporated',
 'Synthetic original-source followup successfully staged into private research without certification.');
end $qa$;
reset role;
do $qa$
declare k text := 'tier_'||md5(current_setting('katoptron.src_case_id'));
begin
 if (select original_source_url from public.flock_community_submissions
   where submission_id=current_setting('katoptron.src_case_id')::uuid)
     <> 'https://example.org/original-citation' then
   raise exception 'Source URL mutated';end if;
 if (select classification from public.flock_point_evidence_cases
   where case_key=k)<>'candidate' then
   raise exception 'Source followup staged directly as verified';end if;
 if katoptron_internal.point_case_public(k) then
   raise exception 'Community source was published without independent verification/consent';end if;
end $qa$;
rollback;
