-- 072: Public directory suppresses redundant legacy undated disclosure rows
-- without mutating reviewed source records or collapsing dated distinct actions.
create view public.flock_accountability_directory
with (security_invoker=true) as
select r.event_key,r.event_type,r.evidence_level,r.jurisdiction_label,
 r.state_code,r.agency_label,r.person_label,r.person_role,r.event_date,
 r.date_basis,r.title,r.summary,r.source_url,r.source_label,r.amount_usd,r.camera_count
from (
 select e.*,
 row_number() over (
   partition by case
    when e.event_type='editorially_reviewed_action' and e.event_date is null
     then 'legacy-disclosure:'||e.source_url||':'||coalesce(e.agency_label,'')
    else e.event_key end
   order by e.event_key
 ) as directory_row_number
 from public.flock_accountability_events e
) r
where r.directory_row_number=1;
revoke all on public.flock_accountability_directory from public,anon,authenticated,service_role;
grant select on public.flock_accountability_directory to anon,authenticated,service_role;
comment on view public.flock_accountability_directory is
'Deduplicated read-only RLS-invoker public government source index. Full reviewed historical rows remain in flock_accountability_events.';
