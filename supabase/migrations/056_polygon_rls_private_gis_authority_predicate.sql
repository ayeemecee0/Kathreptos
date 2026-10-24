-- 056: The public coverage-area RLS policy must NOT query restricted
-- government camera-source tables directly. A narrow read-only predicate
-- returns only an existing verified source's boolean status.
create or replace function public.is_current_flock_polygon_camera_gis_source(
 p_source_key text
) returns boolean language sql stable security definer set search_path=''
as $source_flag$
  select exists(
    select 1 from public.trusted_flock_gis_sources s
    where s.source_key=p_source_key and s.source_status='verified'
  )
$source_flag$;
revoke all on function public.is_current_flock_polygon_camera_gis_source(text)
 from public,anon,authenticated,service_role;
grant execute on function public.is_current_flock_polygon_camera_gis_source(text)
 to anon,authenticated,service_role;

drop policy if exists original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas;
create policy original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas for select to anon,authenticated
 using (
   geometry_status='verified' and (
     (government_source_key is not null and
       public.is_current_flock_polygon_camera_gis_source(government_source_key))
     or
     (government_program_key is not null and exists (
       select 1 from public.flock_documented_programs p
       where p.program_key=government_program_key
         and p.record_status='verified'
         and p.program_status='documented_at_source_date'))
   )
 );
comment on function public.is_current_flock_polygon_camera_gis_source(text)
is 'Read-only boolean status predicate for public Flock polygon RLS. Never exposes private source registry content, editing rights or unverifiable camera geometry.';
