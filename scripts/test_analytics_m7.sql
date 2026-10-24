-- Validate source-only analytics and caller-invoker privacy.
do $$
begin
 if (select count(*) from pg_class
     where oid in ('public.flock_analytics_overview'::regclass,
                   'public.flock_analytics_states'::regclass,
                   'public.flock_analytics_monthly_evidence'::regclass)
       and reloptions @> array['security_invoker=true']::text[])<>3 then
   raise exception 'Analytics views must use caller RLS'; end if;
 if has_table_privilege('anon','public.flock_community_submissions','SELECT')
   or has_table_privilege('anon','public.flock_community_screening','SELECT') then
   raise exception 'Private submissions accidentally exposed'; end if;
end $$;
begin;set local role anon;
do $$
declare m record;
begin
 select * into m from public.flock_analytics_overview;
 if m.exact_government_points<>(select count(*) from public.flock_camera_locations
   where verification_status='verified' and location_accuracy='exact') then
   raise exception 'Analytics camera count differs from verified GIS inventory';end if;
 if m.accountability_records<>(select count(*) from public.flock_accountability_directory) then
   raise exception 'Accountability analytics include hidden/repeated records';end if;
 if m.source_dated_programs<>(select count(*) from public.flock_documented_programs where record_status='verified') then
   raise exception 'Government program analytics incorrectly counted';end if;
 if m.states_with_any_documented_evidence < m.states_with_exact_gis_evidence then
   raise exception 'State-level evidence accounting inconsistent';end if;
 if exists(select 1 from public.flock_analytics_states
    where verified_exact_gis_points<0 or terminated_as_of_source>source_dated_program_records) then
   raise exception 'Invalid state evidence inventory';end if;
 if exists(select 1 from public.flock_analytics_monthly_evidence
   where evidence_month>current_date or source_dated_records<=0) then
   raise exception 'Invalid chronological source-date counts';end if;
end $$;
rollback;
