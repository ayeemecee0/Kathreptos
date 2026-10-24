-- Milestone 6: run after migrations 070 and 071 in disposable PostgreSQL.
do $$
declare n integer;
begin
 if not exists(select 1 from pg_class where oid='public.flock_accountability_events'::regclass
   and reloptions @> array['security_invoker=true']::text[]) then
   raise exception 'Accountability feed must enforce caller row security'; end if;
 if has_table_privilege('anon','public.flock_accountability_roles','INSERT')
   or has_table_privilege('authenticated','public.flock_accountability_roles','UPDATE')
   or has_table_privilege('service_role','public.flock_accountability_roles','INSERT') then
   raise exception 'Untrusted roles can edit personnel claims'; end if;
 if not (select relrowsecurity from pg_class where oid='public.flock_accountability_roles'::regclass) then
   raise exception 'Professional role evidence RLS missing';end if;
 if (select count(*) from public.flock_accountability_roles where review_status='verified')<>3 then
   raise exception 'Expected exactly three initially sourced vendor roles';end if;
 if exists(select 1 from public.flock_accountability_events
   where source_url not like 'https://%' or event_type not in
   ('government_program','editorially_reviewed_action','executed_contract','agency_reported_deployment',
   'agenda_mention','recorded_legislative_decision','contract_form_document')) then
   raise exception 'Accountability feed contains unknown or unsafe source';end if;
 if exists(select 1 from public.flock_accountability_events
   where event_type='agenda_mention' and (evidence_level<>'original_government_agenda_mention_only'
       or person_label is not null)) then
   raise exception 'Agenda matter implied an individual vote';end if;
 if exists(select 1 from public.flock_accountability_events
   where event_type='contract_form_document' and
         evidence_level<>'document_exists_execution_unverified') then
   raise exception 'Unsigned agreement wrongly described as signed';end if;
end $$;
begin;
set local role anon;
do $$
begin
 if not has_table_privilege('anon','public.flock_accountability_events','SELECT')
    or not has_table_privilege('anon','public.flock_accountability_roles','SELECT') then
   raise exception 'Public accountability feeds inaccessible';end if;
 if has_table_privilege('anon','public.flock_accountability_roles','UPDATE') then
   raise exception 'Public personnel edits possible';end if;
 if (select count(*) from public.flock_accountability_roles)<>3 then
   raise exception 'Public role filtering failed';end if;
end $$;
rollback;
