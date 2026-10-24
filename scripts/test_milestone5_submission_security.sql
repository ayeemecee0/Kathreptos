-- Milestone 5 regression: run after migrations 060, 061, 062, 065.
begin;
-- Earlier regression fixtures may already create this synthetic user.
-- Reuse it only in the disposable PostgreSQL CI database, never in production.
-- Create a unique non-reviewer fixture each run so earlier test accounts
-- cannot accidentally grant this test reviewer permissions.
with new_user as (
  insert into auth.users(id) values (gen_random_uuid()) returning id
)
select set_config('request.jwt.claim.sub',id::text,true) from new_user;
set local role authenticated;
do $m5$
declare
 i integer;
 rejected boolean:=false;
begin
 if has_table_privilege('anon','public.flock_community_submissions','INSERT')
    or has_table_privilege('anon','public.flock_community_submissions','SELECT')
    or has_table_privilege('authenticated','public.flock_community_screening','SELECT')
    or has_table_privilege('authenticated','public.flock_community_review_history','SELECT')
    or has_table_privilege('authenticated','public.flock_point_evidence_cases','UPDATE')
 then raise exception 'Milestone 5 private data leak'; end if;
 for i in 1..3 loop
  insert into public.flock_community_submissions(latitude,longitude,description,original_source_url,consent_to_review)
  values (38.55+i/10000.0,-121.4,
  'Synthetic verification report used in rollback-only CI tests, never submitted to the live public queue.','https://example.org/ci-test',true);
 end loop;
 if (select count(*) from public.flock_community_submissions)<>3 then
  raise exception 'Incorrect report count';end if;
 begin
  insert into public.flock_community_submissions(latitude,longitude,description,consent_to_review)
  values (38.56,-121.4,'Fourth synthetic CI submission must be rejected by the daily account rate limit.',true);
 exception when check_violation or raise_exception then rejected:=true;
 end;
 if not rejected then raise exception 'Rate limiter bypass'; end if;
 begin
  perform public.list_community_review_queue(1);
  raise exception 'Reviewer permission bypass';
 exception when insufficient_privilege then null;
 end;
end $m5$;
reset role;
do $admin$
begin
 if (select count(*) from public.flock_community_screening)<>3 then
  raise exception 'Screening trigger missed reports';end if;
 if (select count(*) from public.flock_point_evidence_cases where source_url='https://example.org/ci-test' and classification='candidate')<>3 then raise exception 'Private automatic staging failed';end if;
 if (select count(*) from public.flock_point_evidence_attestations where source_url='https://example.org/ci-test' and evidence_status='staged')<>3 then raise exception 'Unverified attestation staging failed';end if;
 if exists(select 1 from public.flock_point_evidence_cases c
   where c.case_key like 'tier_%' and c.classification<>'candidate'
   and c.staged_at>=now()-interval '1 minute') then
  raise exception 'Community test accidentally published tiered evidence';end if;
end $admin$;
rollback;
