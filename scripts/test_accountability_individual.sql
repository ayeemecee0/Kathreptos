-- Milestone 6: no published official-position claim without a dated primary source.
do $$
begin
 if not (select relrowsecurity from pg_class
   where oid='public.flock_individual_public_positions'::regclass) then
   raise exception 'Official position table is missing RLS';end if;
 if has_table_privilege('anon','public.flock_individual_public_positions','INSERT')
 or has_table_privilege('authenticated','public.flock_individual_public_positions','UPDATE')
 or has_table_privilege('service_role','public.flock_individual_public_positions','INSERT')
 then raise exception 'Untrusted actors could self-certify a public vote';end if;
 if not has_column_privilege('anon','public.flock_individual_public_positions','person_name','SELECT') then
   raise exception 'Sourced public official votes not readable';end if;
end $$;
begin;
insert into public.flock_individual_public_positions(
 position_key,person_name,office_title,jurisdiction_label,state_code,
 record_kind,recorded_position,action_date,document_reference,evidence_description,
 original_government_url,source_kind)
values('rollback_test_official0001','Synthetic Official','Council Member','Example City, CA','CA',
'individual_roll_call_vote','yes',date '2026-01-01','Test roll call document',
'Synthetic unit-test record only, not an authentic Flock Safety vote or identifiable person.',
'https://government.example.gov/rollcall','original_roll_call');
set local role anon;
do $$
begin
 if exists(select 1 from public.flock_individual_public_positions
  where position_key='rollback_test_official0001') then
  raise exception 'Unapproved named government vote leaked to public';end if;
end $$;
reset role;
rollback;
