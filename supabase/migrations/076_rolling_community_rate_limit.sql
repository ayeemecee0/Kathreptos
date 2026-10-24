-- 076: Enforce the published three reports per *rolling* 24 hours.
-- Previous fixed-window bucket logic could permit six reports close to a reset.
-- Owner-locked count includes concurrent new reports and ignores client timestamps.
create or replace function katoptron_internal.throttle_community_report()
returns trigger language plpgsql security definer set search_path=''
as $body$
declare recent_reports integer;
begin
 if (select auth.uid()) is null or new.submitter_id is distinct from (select auth.uid()) then
   raise exception 'Authenticated report owner required' using errcode='42501';
 end if;
 perform pg_catalog.pg_advisory_xact_lock(
   pg_catalog.hashtextextended(new.submitter_id::text,0));
 select count(*) into recent_reports
 from public.flock_community_submissions r
 where r.submitter_id=new.submitter_id and
       r.created_at>=pg_catalog.now()-interval '24 hours';
 if recent_reports >= 3 then
   raise exception 'Maximum 3 reports per rolling 24 hours'
     using errcode='P0001';
 end if;
 return new;
end
$body$;
revoke all on function katoptron_internal.throttle_community_report()
 from public,anon,authenticated,service_role;
comment on function katoptron_internal.throttle_community_report() is
'Private trigger: validates owning authenticated principal and serializes rolling 24h submission count; the historical fixed-window counter is no longer used.';
