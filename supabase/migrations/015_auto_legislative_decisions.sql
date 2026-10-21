-- Independently verified Flock Safety legislative ACTION EVENTS, not contracts.
-- Auto-publication is permitted only for a public Legistar matter previously
-- verified as a direct Flock Safety mention and an explicit action-history
-- decision by an actual legislative body, corroborated by the named pass flag.
--
-- A single matter may have multiple actions on different dates. Publication
-- does NOT claim the most recent or final policy status, signed contracts,
-- camera deployment, individual votes or payments.

create table if not exists public.verified_flock_legislative_decisions (
  tenant text not null check (tenant ~ '^[a-z0-9-]{3,40}$'),
  matter_id bigint not null check (matter_id > 0),
  history_id bigint not null check (history_id > 0),
  jurisdiction_label text not null check (length(btrim(jurisdiction_label)) between 5 and 150),
  matter_title text not null check (length(btrim(matter_title)) between 12 and 1000
                        and matter_title ~* 'flock[[:space:][:punct:]]+safety'),
  file_number text check (file_number is null or length(file_number) <= 160),
  action_name text not null check (length(btrim(action_name)) between 5 and 100),
  action_body text not null check (length(btrim(action_body)) between 5 and 120),
  passed_flag_name text not null check (length(btrim(passed_flag_name)) between 3 and 30),
  decision_outcome text not null
    check (decision_outcome in ('adopted','adopted_as_amended','approved',
                                'approved_as_amended','failed','rejected')),
  action_date date not null check (action_date >= date '1990-01-01'
                  and action_date <= current_date + 1),
  official_matter_url text generated always as
    ('https://webapi.legistar.com/v1/' || tenant || '/matters/' || matter_id::text) stored,
  official_history_url text generated always as
    ('https://webapi.legistar.com/v1/' || tenant || '/matters/' ||
        matter_id::text || '/histories/' || history_id::text) stored,
  verified_at timestamptz not null default now(),
  verification_method text not null
    default 'official_legistar_history_exact_action_and_flag_v1'
    check (verification_method='official_legistar_history_exact_action_and_flag_v1'),
  status text not null default 'verified' check (status in ('verified','revoked')),
  primary key (tenant,matter_id,history_id),
  foreign key (tenant,matter_id)
    references public.verified_flock_agenda_mentions(tenant,matter_id)
    on delete restrict,
  constraint exact_decision_action_check check (
    (decision_outcome='adopted' and lower(btrim(action_name))='adopted')
    or (decision_outcome='adopted_as_amended' and lower(btrim(action_name))='adopted as amended')
    or (decision_outcome='approved' and lower(btrim(action_name))='approved')
    or (decision_outcome='approved_as_amended' and lower(btrim(action_name))='approved as amended')
    or (decision_outcome='failed' and lower(btrim(action_name))='failed')
    or (decision_outcome='rejected' and lower(btrim(action_name))='rejected')
  ),
  constraint matching_pass_flag_check check (
    (decision_outcome in ('adopted','adopted_as_amended','approved','approved_as_amended')
      and lower(btrim(passed_flag_name)) in ('pass','passed'))
    or (decision_outcome in ('failed','rejected')
      and lower(btrim(passed_flag_name)) in ('fail','failed'))
  ),
  constraint governing_body_check check (
    lower(btrim(action_body)) in (
      'city council','common council','county council','county board',
      'board of supervisors','board of county commissioners',
      'city commission','county commission','town council','village board',
      'municipal council','city council of the city of oakland'
    )
  )
);

create index if not exists verified_flock_legislative_decisions_time_idx
  on public.verified_flock_legislative_decisions(action_date desc,tenant);

create or replace function public.guard_auto_verified_legislative_decision()
returns trigger
language plpgsql security definer
set search_path = ''
as $government_decision_guard$
declare
  v_title text;
  v_label text;
  v_status text;
  v_registry_status text;
  v_current_label text;
begin
  if tg_op = 'UPDATE' then
    if (new.tenant,new.matter_id,new.history_id,new.jurisdiction_label,
        new.matter_title,new.file_number,new.action_name,new.action_body,
        new.passed_flag_name,new.decision_outcome,new.action_date,
        new.verified_at,new.verification_method)
       is distinct from
       (old.tenant,old.matter_id,old.history_id,old.jurisdiction_label,
        old.matter_title,old.file_number,old.action_name,old.action_body,
        old.passed_flag_name,old.decision_outcome,old.action_date,
        old.verified_at,old.verification_method) then
      raise exception 'Government decision evidence is immutable; revoke, then review';
    end if;
    if old.status='revoked' and new.status='verified' then
      raise exception 'Revoked decisions cannot be silently republished';
    end if;
    return new;
  end if;

  select matter_title,jurisdiction_label,status into v_title,v_label,v_status
    from public.verified_flock_agenda_mentions
    where tenant=new.tenant and matter_id=new.matter_id;
  if v_status is distinct from 'verified'
      or v_label is distinct from new.jurisdiction_label
      or v_title is distinct from new.matter_title then
    raise exception 'Official Flock matter not independently verified';
  end if;
  select verification_status,jurisdiction_label
    into v_registry_status,v_current_label
    from public.government_source_registry
    where source_kind='legistar'
      and source_url='https://' || new.tenant || '.legistar.com/';
  if v_registry_status is distinct from 'verified'
      or v_current_label is distinct from new.jurisdiction_label then
    raise exception 'Legistar government authority is no longer verified';
  end if;
  if new.status <> 'verified' then
    raise exception 'New legislative decisions must be independently verified';
  end if;
  return new;
end;
$government_decision_guard$;

drop trigger if exists guard_auto_verified_legislative_decision
  on public.verified_flock_legislative_decisions;
create trigger guard_auto_verified_legislative_decision
before insert or update on public.verified_flock_legislative_decisions
for each row execute function public.guard_auto_verified_legislative_decision();

-- Revocation of a previously verified Flock agenda matter immediately hides
-- every dependent decision event while preserving its original evidence.
create or replace function public.withdraw_legislative_decisions_on_matter_revocation()
returns trigger language plpgsql security definer
set search_path = ''
as $withdraw_government_decisions$
begin
  if old.status='verified' and new.status='revoked' then
    update public.verified_flock_legislative_decisions
      set status='revoked'
      where tenant=old.tenant and matter_id=old.matter_id
        and status='verified';
  end if;
  return new;
end;
$withdraw_government_decisions$;

drop trigger if exists withdraw_legislative_decisions_on_matter_revocation
  on public.verified_flock_agenda_mentions;
create trigger withdraw_legislative_decisions_on_matter_revocation
after update on public.verified_flock_agenda_mentions
for each row execute function public.withdraw_legislative_decisions_on_matter_revocation();

alter table public.verified_flock_legislative_decisions enable row level security;
revoke all on public.verified_flock_legislative_decisions from anon,authenticated;
grant select on public.verified_flock_legislative_decisions to anon,authenticated;
revoke update,delete on public.verified_flock_legislative_decisions from service_role;
grant select,insert on public.verified_flock_legislative_decisions to service_role;

drop policy if exists verified_government_legislative_decisions_public
  on public.verified_flock_legislative_decisions;
create policy verified_government_legislative_decisions_public
on public.verified_flock_legislative_decisions
for select to anon,authenticated using (
  status='verified' and exists (
    select 1 from public.verified_flock_agenda_mentions m
    where m.tenant=tenant and m.matter_id=matter_id
      and m.status='verified'
  )
);

comment on table public.verified_flock_legislative_decisions is
'Distinct, dated government legislative action events, automatically verified against both named action and matching pass/fail flag. NOT signed contracts, deployments, final policy statuses or individual votes.';
