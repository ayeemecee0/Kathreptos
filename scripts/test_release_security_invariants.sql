-- Release safety invariants: account data can never become public by schema drift.
do $audit$
declare rel text; p record;
begin
 foreach rel in array array[
  'flock_community_submissions','flock_community_screening',
  'flock_community_review_history','flock_point_evidence_cases',
  'flock_point_evidence_attestations','editorial_reviewers'
 ] loop
  if has_table_privilege('anon',format('public.%I',rel),'SELECT')
    or has_table_privilege('anon',format('public.%I',rel),'INSERT')
    or has_table_privilege('anon',format('public.%I',rel),'UPDATE')
    or has_table_privilege('anon',format('public.%I',rel),'DELETE') then
   raise exception 'Anonymous access regression in private source table %',rel;
  end if;
 end loop;
 if not (select relrowsecurity from pg_class
  where oid='public.flock_community_submissions'::regclass) then
  raise exception 'Contributor RLS disabled';
 end if;
 if has_column_privilege('authenticated','public.flock_community_submissions','submitter_id','SELECT')
    or has_column_privilege('authenticated','public.flock_community_submissions','report_status','UPDATE')
    or has_column_privilege('authenticated','public.flock_community_submissions','publication_consent','UPDATE')
    or has_table_privilege('authenticated','public.editorial_reviewers','SELECT') then
   raise exception 'Contributor elevated into reviewer/owner metadata';
 end if;
 for p in select oid::regprocedure::text as signature,oid from pg_proc
   where pronamespace='public'::regnamespace
     and proname in ('editorial_decide','editorial_session','list_community_review_queue',
       'set_community_review_status','withdraw_own_community_report',
       'community_report_attachment_paths')
 loop
  if has_function_privilege('anon',p.oid,'EXECUTE') then
   raise exception 'Anonymous ability to execute sensitive RPC %',p.signature;
  end if;
 end loop;
 if has_function_privilege('authenticated',
   'public.set_community_review_status(uuid,text)'::regprocedure,'EXECUTE') then
   raise exception 'Legacy no-audit reviewer RPC re-enabled';
 end if;
 if to_regclass('storage.objects') is not null then
   if (select public from storage.buckets where id='katoptron-community-evidence') then
    raise exception 'Private photographic evidence bucket has been made public';
   end if;
   if exists(select 1 from pg_policies where schemaname='storage' and tablename='objects'
        and policyname like 'katoptron_%' and 'anon'=any(roles)) then
    raise exception 'Anonymous Storage evidence access';
   end if;
 end if;
end
$audit$;
-- Reconcile the public map solely to independently source-verified records.
begin;set local role anon;
do $anon$
declare m record;
begin
 select * into m from public.flock_analytics_overview;
 if m.exact_government_points<>(select count(*) from public.flock_camera_locations
    where verification_status='verified' and location_accuracy='exact') then
    raise exception 'Public GIS source/count reconciliation failure';
 end if;
 if m.documented_individual_positions<>(select count(*) from public.flock_individual_public_positions) then
    raise exception 'Unreviewed named official claims exposed';
 end if;
end
$anon$;
rollback;
