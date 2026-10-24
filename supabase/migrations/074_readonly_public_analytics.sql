-- 074: Zero-cost, source-only public analytics. Security-invoker RLS.
create or replace view public.flock_analytics_overview with (security_invoker=true) as
select
 (select count(*)::integer from public.flock_camera_locations where verification_status='verified' and location_accuracy='exact') as exact_government_points,
 (select count(*)::integer from public.flock_public_tiered_camera_points) as separately_corroborated_points,
 (select count(*)::integer from public.flock_documented_programs where record_status='verified') as source_dated_programs,
 (select count(*)::integer from public.flock_documented_programs where record_status='verified' and program_status='terminated_at_source_date') as terminated_at_source_date,
 (select count(*)::integer from public.flock_accountability_directory) as accountability_records,
 (select count(*)::integer from public.flock_accountability_directory where event_type='executed_contract') as documented_signed_contracts,
 (select count(*)::integer from public.flock_individual_public_positions) as documented_individual_positions,
 (select count(*)::integer from public.flock_accountability_roles) as sourced_professional_roles,
 (select count(*)::integer from public.flock_public_state_evidence_index where verified_camera_points>0) as states_with_exact_gis_evidence,
 (select count(*)::integer from public.flock_public_state_evidence_index where dated_program_records>0 or verified_camera_points>0) as states_with_any_documented_evidence;
revoke all on public.flock_analytics_overview from public,anon,authenticated,service_role;
grant select on public.flock_analytics_overview to anon,authenticated,service_role;

create or replace view public.flock_analytics_states with (security_invoker=true) as
with types as (
 select e.state_code,count(*)::integer as total_accountability_records,
 count(*) filter(where e.event_type='agenda_mention')::integer as agenda_mentions,
 count(*) filter(where e.event_type='executed_contract')::integer as documented_signed_contracts
 from public.flock_accountability_directory e
 where e.state_code ~ '^[A-Z]{2}$' group by e.state_code
)
select s.state_code,
 s.verified_camera_points::integer as verified_exact_gis_points,
 s.verified_camera_jurisdictions::integer as verified_point_jurisdictions,
 s.dated_program_records::integer as source_dated_program_records,
 s.terminated_program_records::integer as terminated_as_of_source,
 coalesce(t.total_accountability_records,0)::integer as accountability_records,
 coalesce(t.agenda_mentions,0)::integer as agenda_mentions,
 coalesce(t.documented_signed_contracts,0)::integer as signed_contracts
from public.flock_public_state_evidence_index s
left join types t on t.state_code=s.state_code;
revoke all on public.flock_analytics_states from public,anon,authenticated,service_role;
grant select on public.flock_analytics_states to anon,authenticated,service_role;

create or replace view public.flock_analytics_monthly_evidence with (security_invoker=true) as
select date_trunc('month',e.event_date)::date as evidence_month,
 e.event_type, count(*)::integer as source_dated_records
from public.flock_accountability_directory e
where e.event_date is not null and e.event_date<=current_date
group by date_trunc('month',e.event_date)::date,e.event_type;
revoke all on public.flock_analytics_monthly_evidence from public,anon,authenticated,service_role;
grant select on public.flock_analytics_monthly_evidence to anon,authenticated,service_role;
comment on view public.flock_analytics_monthly_evidence is
'Frequency of source-dated government records, NOT camera installations or changes in surveillance volume. Undated records are excluded and not guessed.';
