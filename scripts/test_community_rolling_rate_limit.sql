-- Rolling-rate boundary test; synthetic records exist only inside this transaction.
begin;
select set_config('katoptron.rate_test_user',gen_random_uuid()::text,true);
insert into auth.users(id) values(current_setting('katoptron.rate_test_user')::uuid);
select set_config('request.jwt.claim.sub',current_setting('katoptron.rate_test_user'),true);
set local role authenticated;
do $limit$
declare i int;
begin
 for i in 1..3 loop
  insert into public.flock_community_submissions(latitude,longitude,description,consent_to_review)
  values(38.5 + i/10000.0,-121.41,
   'This is a synthetic rolling-window rate-limit boundary test; never an observed camera.',true);
 end loop;
end $limit$;
reset role;
-- Simulate reports placed just inside the previous 24 hours, but a legacy
-- fixed-window counter that would otherwise reset and erroneously allow 4th.
update public.flock_community_submissions set created_at=now()-interval '23 hours 59 minutes'
where submitter_id=current_setting('katoptron.rate_test_user')::uuid;
update public.flock_submission_rate_buckets set window_started_at=now()-interval '25 hours'
where user_id=current_setting('katoptron.rate_test_user')::uuid;
set local role authenticated;
do $limit$
begin
 begin
  insert into public.flock_community_submissions(latitude,longitude,description,consent_to_review)
  values(38.51,-121.41,'This is the fourth synthetic report within a rolling 24-hour period and must be rejected.',true);
  raise exception 'FAIL: fourth report was accepted';
 exception when raise_exception then
  if sqlerrm not like 'Maximum 3 reports per rolling 24 hours%' then raise;end if;
 end;
end $limit$;
reset role;
do $limit$
begin
 if (select count(*) from public.flock_community_submissions
     where submitter_id=current_setting('katoptron.rate_test_user')::uuid)<>3 then
   raise exception 'Failed rolling quota check modified reports';
 end if;
end $limit$;
rollback;
