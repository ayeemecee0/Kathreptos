-- Map-first Katoptron schema. All exact coordinates must be backed by
-- source-specific evidence; approximate records denote uncertainty regions,
-- not invented individual cameras. Incomplete coverage is never negative proof.
create table if not exists public.flock_camera_locations (
  id uuid primary key default gen_random_uuid(),
  record_key text not null unique check (length(record_key) between 8 and 200),
  label text not null check (length(btrim(label)) between 5 and 160),
  jurisdiction_label text not null check (length(btrim(jurisdiction_label)) between 3 and 180),
  latitude double precision not null check (latitude between 17 and 72),
  longitude double precision not null check (longitude between -180 and -64),
  location_accuracy text not null check (location_accuracy in ('exact','approximate')),
  uncertainty_radius_m integer not null check (
    (location_accuracy='exact' and uncertainty_radius_m=0)
    or (location_accuracy='approximate'
        and uncertainty_radius_m between 250 and 80000)
  ),
  source_type text not null check
    (source_type in ('official_government','public_dataset','corroborated_community')),
  source_url text not null check (
    length(source_url) between 16 and 2048 and
    source_url ~ '^https://[A-Za-z0-9.-]+(/|$)'
  ),
  evidence_summary text not null check(length(btrim(evidence_summary)) between 30 and 1200),
  evidence_sha256 text not null check(evidence_sha256 ~ '^[0-9a-f]{64}$'),
  verification_method text not null check (
    verification_method in (
      'official_georeferenced_camera_record_v1',
      'cross_source_public_dataset_v1',
      'corroborated_observation_v1',
      'official_jurisdiction_coverage_v1'
    )
  ),
  first_documented_on date,
  last_confirmed_on date,
  published_at timestamptz not null default now(),
  verification_status text not null default 'verified'
    check (verification_status in ('verified','revoked')),
  check (
    (location_accuracy='approximate' and
      verification_method='official_jurisdiction_coverage_v1')
    or (location_accuracy='exact' and
      verification_method<>'official_jurisdiction_coverage_v1')
  ),
  check (last_confirmed_on is null or first_documented_on is null
         or last_confirmed_on >= first_documented_on)
);

create index if not exists flock_camera_geo_idx on public.flock_camera_locations
  (latitude,longitude) where verification_status='verified';
create index if not exists flock_camera_published_idx on public.flock_camera_locations
  (published_at desc) where verification_status='verified';

create or replace function public.guard_verified_flock_camera()
returns trigger language plpgsql set search_path=''
as $$
begin
  if tg_op='UPDATE' then
    if (new.id,new.record_key,new.label,new.jurisdiction_label,new.latitude,
        new.longitude,new.location_accuracy,new.uncertainty_radius_m,
        new.source_type,new.source_url,new.evidence_summary,new.evidence_sha256,
        new.verification_method,new.first_documented_on,new.last_confirmed_on,
        new.published_at)
       is distinct from
       (old.id,old.record_key,old.label,old.jurisdiction_label,old.latitude,
        old.longitude,old.location_accuracy,old.uncertainty_radius_m,
        old.source_type,old.source_url,old.evidence_summary,old.evidence_sha256,
        old.verification_method,old.first_documented_on,old.last_confirmed_on,
        old.published_at) then
      raise exception 'Published camera evidence is immutable: revoke and reverify';
    end if;
    if old.verification_status='revoked' and new.verification_status='verified' then
      raise exception 'Revoked camera evidence cannot be silently republished';
    end if;
    return new;
  end if;
  if new.verification_status <> 'verified' then
    raise exception 'New camera location requires source verification';
  end if;
  return new;
end;
$$;
drop trigger if exists guard_verified_flock_camera on public.flock_camera_locations;
create trigger guard_verified_flock_camera
before insert or update on public.flock_camera_locations
for each row execute function public.guard_verified_flock_camera();

alter table public.flock_camera_locations enable row level security;
revoke all on public.flock_camera_locations from anon,authenticated,service_role;
grant select on public.flock_camera_locations to anon,authenticated;
grant select,insert on public.flock_camera_locations to service_role;
grant update(verification_status) on public.flock_camera_locations to service_role;
drop policy if exists only_verified_flock_camera_locations on public.flock_camera_locations;
create policy only_verified_flock_camera_locations
on public.flock_camera_locations for select to anon,authenticated
using (verification_status='verified');

comment on table public.flock_camera_locations is
'Source-verifiable Flock Safety camera or uncertainty-area coordinates. Empty is expected until location-specific official or independently corroborated evidence has been checked. Approximate areas do not establish camera position or operational status.';
