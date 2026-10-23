-- 044: Public map evidence totals, filtered by verified current data.
-- SECURITY INVOKER respects RLS on underlying camera, polygon and program data.
create or replace view public.flock_public_coverage_stats with (security_invoker=true) as
 select
   (select count(*)::integer from public.flock_camera_locations c where c.verification_status='verified' and c.location_accuracy='exact') as verified_camera_points,
   (select count(distinct c.jurisdiction_label)::integer from public.flock_camera_locations c where c.verification_status='verified' and c.location_accuracy='exact') as verified_point_jurisdictions,
   (select count(*)::integer from public.flock_camera_locations c where c.verification_status='verified' and c.location_accuracy='approximate') as approximate_location_records,
   (select count(*)::integer from public.flock_documented_coverage_areas a where a.geometry_status='verified') as verified_area_polygons,
   (select count(*)::integer from public.flock_documented_programs p where p.record_status='verified') as documented_government_programs;
revoke all on public.flock_public_coverage_stats from public,anon,authenticated,service_role;
grant select on public.flock_public_coverage_stats to anon,authenticated,service_role;
comment on view public.flock_public_coverage_stats is
'Source-verified national evidence counts only. Does not assert complete nationwide coverage or camera operation.';
