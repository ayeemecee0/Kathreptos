-- Fully automated, narrowly verifiable OFFICIAL Flock Safety agenda mentions.
-- An agenda mention is not evidence of a vote, approval, contract execution,
-- camera deployment or vendor payment. Those remain separate fact types.
--
-- Only the unattended verifier may add a new mention after checking the
-- live, PUBLIC Legistar matter on a previously verified government tenant.
-- No automatically discovered material enters public.actions/contracts/deployments.

create table if not exists public.verified_flock_agenda_mentions (
  tenant text not null check (tenant ~ '^[a-z0-9-]{3,40}$'),
  matter_id bigint not null check (matter_id > 0),
  jurisdiction_label text not null check (length(btrim(jurisdiction_label)) >= 5),
  matter_title text not null check (
    length(matter_title) between 12 and 1000
    and matter_title ~* 'flock[[:space:][:punct:]]+safety'
  ),
  file_number text check (file_number is null or length(file_number) <= 160),
  official_api_url text generated always as
    ('https://webapi.legistar.com/v1/' || tenant || '/matters/' || matter_id::text) stored,
  registry_source_url text generated always as
    ('https://' || tenant || '.legistar.com/') stored,
  government_evidence_url text not null check (government_evidence_url ~ '^https://'),
  intro_date date,
  verified_at timestamptz not null default now(),
  verification_method text not null default 'official_api_exact_flock_title_v1'
    check (verification_method = 'official_api_exact_flock_title_v1'),
  status text not null default 'verified' check (status in ('verified','revoked')),
  primary key (tenant,matter_id)
);
create index if not exists verified_flock_agenda_mentions_date_idx
  on public.verified_flock_agenda_mentions (intro_date desc,verified_at desc);

-- Runtime guard verifies that the primary government source is still
-- approved and that this matter was already staged in the private queue.
create or replace function public.guard_auto_verified_flock_agenda_mention()
returns trigger language plpgsql security definer set search_path = ''
as $guard_auto_agenda$
declare
  v_label text;
  v_evidence text;
  v_status text;
begin
  if tg_op = 'UPDATE' then
    if (new.tenant,new.matter_id,new.jurisdiction_label,new.matter_title,
        new.file_number,new.government_evidence_url,new.intro_date,
        new.verified_at,new.verification_method)
       is distinct from
       (old.tenant,old.matter_id,old.jurisdiction_label,old.matter_title,
        old.file_number,old.government_evidence_url,old.intro_date,
        old.verified_at,old.verification_method) then
      raise exception 'Verified agenda provenance is immutable; revoke instead of rewriting';
    end if;
    if old.status = 'revoked' and new.status = 'verified' then
      raise exception 'Revoked government agenda mentions cannot be silently reapproved';
    end if;
    -- Service-role UPDATE/DELETE privileges are independently revoked.
    -- This security-definer trigger checks private provenance as its owner.
    return new;
  end if;

  select verification_status,jurisdiction_label,evidence_url
    into v_status,v_label,v_evidence
    from public.government_source_registry
    where source_url='https://' || new.tenant || '.legistar.com/'
      and source_kind='legistar';
  if v_status is distinct from 'verified'
      or v_label is distinct from new.jurisdiction_label
      or v_evidence is distinct from new.government_evidence_url then
    raise exception 'Government tenant/evidence no longer independently verified';
  end if;
  if not exists(
    select 1 from public.agenda_evidence_reviews r
    join public.discovery_queue q on q.id=r.discovery_queue_id
    where r.tenant=new.tenant and r.matter_id=new.matter_id
      and r.review_state <> 'rejected' and q.status <> 'rejected'
      and r.official_api_url='https://webapi.legistar.com/v1/' ||
        new.tenant || '/matters/' || new.matter_id::text
  ) then
    raise exception 'Public mention requires a previously staged, nonrejected official API matter';
  end if;
  if new.status <> 'verified' then
    raise exception 'New agenda mentions must first pass exact official-source verification';
  end if;
  return new;
end;
$guard_auto_agenda$;

drop trigger if exists guard_auto_verified_flock_agenda_mention
  on public.verified_flock_agenda_mentions;
create trigger guard_auto_verified_flock_agenda_mention
before insert or update on public.verified_flock_agenda_mentions
for each row execute function public.guard_auto_verified_flock_agenda_mention();

alter table public.verified_flock_agenda_mentions enable row level security;
revoke all on public.verified_flock_agenda_mentions from anon,authenticated;
grant select on public.verified_flock_agenda_mentions to anon,authenticated;
-- The unattended service role may add a new independently verified mention,
-- but cannot overwrite or delete an existing publication.
revoke update,delete on public.verified_flock_agenda_mentions from service_role;
grant select,insert on public.verified_flock_agenda_mentions to service_role;
create policy public_verified_flock_agenda_mentions
  on public.verified_flock_agenda_mentions for select
  to anon,authenticated using(status='verified');

comment on table public.verified_flock_agenda_mentions is
  'Automated official Legistar records explicitly naming Flock Safety. These are only agenda mentions, never evidence of approval, signed contract, deployment, or individual vote.';
