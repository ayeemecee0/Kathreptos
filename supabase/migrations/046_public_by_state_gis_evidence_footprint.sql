-- 046 - National camera-source footprint by state abbreviation.
-- SECURITY INVOKER prevents counts from ever including unpublished/withdrawn
-- source records. Jurisdiction names lacking a verified US postal suffix
-- are omitted from the state footprint, not placed into an invented state.
create or replace view public.flock_public_state_evidence
with (security_invoker=true)
as
select
 substring(c.jurisdiction_label from ', ([A-Z]{2})$') as state_code,
 count(*)::integer as verified_camera_points,
 count(distinct c.jurisdiction_label)::integer as verified_jurisdictions
from public.flock_camera_locations c
where c.verification_status='verified'
  and c.location_accuracy='exact'
  and c.jurisdiction_label ~ ', [A-Z]{2}$'
group by substring(c.jurisdiction_label from ', ([A-Z]{2})$');
revoke all on public.flock_public_state_evidence
 from public,anon,authenticated,service_role;
grant select on public.flock_public_state_evidence
 to anon,authenticated,service_role;
comment on view public.flock_public_state_evidence is
'Public-sourced GIS camera point count by known state suffix. A missing state row means no source-verified point in this partial Katoptron inventory, NOT evidence of no Flock cameras in the state.';
