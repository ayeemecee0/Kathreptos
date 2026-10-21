-- Automatically verify *recorded legislative actions* from official Legistar
-- MatterHistory entries. These are action-level facts with the recorded vote
-- outcome AND acting government body; never a signed contract or deployment.
--
-- The workflow credential can only INSERT new, validated facts; it cannot
-- rewrite or delete them. Source revocation hides dependent actions through
-- the SELECT policy without destroying their audit provenance.

create table if not exists public.verified_flock_legislative_actions (
  tenant text not null check (tenant ~ '^[a-z0-9-]{3,40}$'),
  matter_id bigint not null check (matter_id > 0),
  history_id bigint not null check (history_id > 0),
  jurisdiction_label text not null check (length(btrim(jurisdiction_label)) >= 5),
  matter_title text not null check (length(matter_title) between 12 and 1000),
  file_number text check (file_number is null or length(file_number) <= 160),
  action_date date not null check (action_date between date '1990-01-01' and date '2100-01-01'),
  acting_body text not null check (length(btrim(acting_body)) between 4 and 250),
  body_scope text not null check (body_scope in ('governing_body','committee')),
  recorded_action_name text not null check (length(btrim(recorded_action_name)) between 4 and 300),
  outcome text not null check (outcome in (
    'adopted', 'adopted_as_amended', 'approved', 'motion_failed',
    'discussed_and_closed', 'received_and_filed')),
  passed_flag integer check (passed_flag in (0,1)),
  passed_flag_name text check (passed_flag_name in ('Pass','Fail')),
  official_history_url text generated always as (
    'https://webapi.legistar.com/v1/' || tenant || '/matters/' ||
    matter_id::text || '/histories/' || history_id::text
  ) stored,
  verification_method text not null default 'official_legistar_history_action_v1'
    check (verification_method='official_legistar_history_action_v1'),
  verified_at timestamptz not null default now(),
  status text not null default 'verified' check(status in ('verified','revoked')),
  primary key (tenant,matter_id,history_id),
  foreign key (tenant,matter_id)
    references public.verified_flock_agenda_mentions(tenant,matter_id),
  check (
    -- A failed *motion* is not an adopted resolution; the literal passed flag
    -- overrides misleading positive-sounding action labels ("Approved ...").
    (outcome='motion_failed' and passed_flag=0 and passed_flag_name='Fail'
       and recorded_action_name ~* '^(approved|adopted|passed|rejected|failed|denied|motion[[:space:]])')
    or
    (body_scope='governing_body' and passed_flag=1 and passed_flag_name='Pass' and
      ((outcome='adopted' and lower(recorded_action_name)='adopted')
      or (outcome='adopted_as_amended' and lower(recorded_action_name)='adopted as amended')
      or (outcome='approved' and lower(recorded_action_name)='approved')))
    or
    (body_scope='governing_body' and passed_flag is null and passed_flag_name is null and
      ((outcome='discussed_and_closed' and lower(recorded_action_name)='discussed and closed')
      or (outcome='received_and_filed' and lower(recorded_action_name)='received and filed')))
  )
);

create index if not exists verified_flock_legislative_actions_dates
  on public.verified_flock_legislative_actions(action_date desc,tenant,matter_id);

create or replace function public.guard_verified_flock_legislative_action()
returns trigger language plpgsql security definer set search_path = ''
as $decision_guard$
declare
  m record;
begin
  if tg_op = 'UPDATE' then
    if (new.tenant,new.matter_id,new.history_id,new.jurisdiction_label,
        new.matter_title,new.file_number,new.action_date,new.acting_body,
        new.body_scope,new.recorded_action_name,new.outcome,new.passed_flag,
        new.passed_flag_name,new.verification_method,new.verified_at)
       is distinct from
       (old.tenant,old.matter_id,old.history_id,old.jurisdiction_label,
        old.matter_title,old.file_number,old.action_date,old.acting_body,
        old.body_scope,old.recorded_action_name,old.outcome,old.passed_flag,
        old.passed_flag_name,old.verification_method,old.verified_at) then
      raise exception 'Verified action provenance is immutable';
    end if;
    if old.status='revoked' and new.status='verified' then
      raise exception 'Revoked actions cannot be silently reapproved';
    end if;
    return new;
  end if;
  select jurisdiction_label,matter_title,file_number,status into m
    from public.verified_flock_agenda_mentions
    where tenant=new.tenant and matter_id=new.matter_id;
  if not found or m.status <> 'verified'
      or m.jurisdiction_label is distinct from new.jurisdiction_label
      or m.matter_title is distinct from new.matter_title
      or m.file_number is distinct from new.file_number then
    raise exception 'Official source mention missing, revoked, or identity changed';
  end if;
  if new.status <> 'verified' then
    raise exception 'New actions must have passed live official history verification';
  end if;
  return new;
end;
$decision_guard$;

drop trigger if exists guard_verified_flock_legislative_action
  on public.verified_flock_legislative_actions;
create trigger guard_verified_flock_legislative_action
before insert or update on public.verified_flock_legislative_actions
for each row execute function public.guard_verified_flock_legislative_action();

alter table public.verified_flock_legislative_actions enable row level security;
revoke all on public.verified_flock_legislative_actions from anon,authenticated;
grant select on public.verified_flock_legislative_actions to anon,authenticated;

-- Any revoked government source automatically removes dependent decisions
-- from public queries, because the corresponding verified agenda mention is
-- withdrawn by migrations 013/014. There is no public write policy.
create policy public_verified_flock_legislative_actions
on public.verified_flock_legislative_actions
for select to anon,authenticated
using (
  status='verified' and exists (
    select 1 from public.verified_flock_agenda_mentions m
    where m.tenant=verified_flock_legislative_actions.tenant
      and m.matter_id=verified_flock_legislative_actions.matter_id
      and m.status='verified'
  )
);

-- Scheduled verifier uses service-role permissions, but cannot override an
-- existing published action or its revocation.
revoke update,delete on public.verified_flock_legislative_actions from service_role;
grant select,insert on public.verified_flock_legislative_actions to service_role;

comment on table public.verified_flock_legislative_actions is
  'Independently re-fetched official Legistar event history actions. Recorded motion outcomes are scoped to the named body, not proof of contract execution or deployment.';
