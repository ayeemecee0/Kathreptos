-- 045: The original deployment-area RLS policy used a direct subquery
-- against a private GIS source registry, so anonymous SELECT hit permission
-- denied even when no areas existed. Expose ONLY the current-source boolean.
create or replace function public.official_flock_area_source_is_current(
  p_source_key text
) returns boolean
language sql stable security definer set search_path=''
as $$
  select exists (
    select 1 from public.trusted_flock_gis_sources s
    where s.source_key=p_source_key and s.source_status='verified'
  );
$$;
revoke all on function public.official_flock_area_source_is_current(text)
 from public,anon,authenticated,service_role;
grant execute on function public.official_flock_area_source_is_current(text)
 to anon,authenticated,service_role;
drop policy if exists original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas;
create policy original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas
 for select to anon,authenticated using (
   geometry_status='verified'
   and public.official_flock_area_source_is_current(government_source_key)
 );
comment on function public.official_flock_area_source_is_current(text) is
'RLS-safe boolean only: allow the public map to read a verified original Flock deployment area without granting SELECT on the private GIS authority registry.';
