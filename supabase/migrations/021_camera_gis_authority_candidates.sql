-- 021: maintain source authority on the public map; stage candidate official
-- GIS portals without treating an ArcGIS title as government endorsement.
create or replace function public.gis_camera_authority_current(
  p_url text, p_jurisdiction text)
returns boolean language sql stable security definer set search_path=''
as $$
  select exists (
    select 1 from public.trusted_flock_gis_sources s
    where s.gis_layer_url=p_url and s.jurisdiction_label=p_jurisdiction
      and s.source_status='verified'
  )
$$;
revoke all on function public.gis_camera_authority_current(text,text) from public;
grant execute on function public.gis_camera_authority_current(text,text) to anon,authenticated,service_role;

create or replace function public.check_camera_source_on_insert()
returns trigger language plpgsql security definer set search_path=''
as $$
begin
  if new.verification_method='official_georeferenced_camera_record_v1' and
    (new.source_type <> 'official_government' or
     not public.gis_camera_authority_current(new.source_url,new.jurisdiction_label)) then
    raise exception 'Official GIS camera requires currently verified jurisdiction/source authority';
  end if;
  return new;
end;
$$;
drop trigger if exists check_camera_source_on_insert on public.flock_camera_locations;
create trigger check_camera_source_on_insert
before insert on public.flock_camera_locations
for each row execute function public.check_camera_source_on_insert();

drop policy if exists only_verified_flock_camera_locations on public.flock_camera_locations;
create policy only_verified_flock_camera_locations
on public.flock_camera_locations for select to anon,authenticated
using (
  verification_status='verified'
  and (
    verification_method <> 'official_georeferenced_camera_record_v1'
    or public.gis_camera_authority_current(source_url,jurisdiction_label)
  )
);

create or replace function public.revoke_cameras_on_gis_source_revocation()
returns trigger language plpgsql security definer set search_path=''
as $$
begin
  if old.source_status='verified' and new.source_status <> 'verified' then
    update public.flock_camera_locations
       set verification_status='revoked'
     where source_url=old.gis_layer_url
       and verification_method='official_georeferenced_camera_record_v1'
       and verification_status='verified';
  end if;
  return new;
end;
$$;
drop trigger if exists revoke_cameras_on_gis_source_revocation
 on public.trusted_flock_gis_sources;
create trigger revoke_cameras_on_gis_source_revocation
after update of source_status on public.trusted_flock_gis_sources
for each row execute function public.revoke_cameras_on_gis_source_revocation();

create table if not exists public.flock_gis_source_candidates (
  gis_layer_url text primary key check(
    length(gis_layer_url) between 30 and 2048
    and gis_layer_url ~ '^https://[A-Za-z0-9.-]+/.+/(FeatureServer|MapServer)/[0-9]+$'),
  layer_name text not null check(length(layer_name) between 3 and 180),
  geometry_type text not null check(length(geometry_type) between 5 and 65),
  object_id_field text not null check(length(object_id_field) between 2 and 65),
  layer_purpose text not null check(length(layer_purpose) between 15 and 500),
  public_gov_context_url text,
  first_discovered_at timestamptz not null default now(),
  last_checked_at timestamptz not null default now(),
  trust_status text not null default 'unverified'
    check (trust_status in ('unverified','rejected')),
  check (public_gov_context_url is null or
    public_gov_context_url ~ '^https://[A-Za-z0-9.-]+/[^[:space:]]+$'),
  check(last_checked_at >= first_discovered_at)
);
alter table public.flock_gis_source_candidates enable row level security;
revoke all on public.flock_gis_source_candidates from anon,authenticated,service_role;
grant select,insert on public.flock_gis_source_candidates to service_role;
grant update(last_checked_at) on public.flock_gis_source_candidates to service_role;
comment on table public.flock_gis_source_candidates is
'Private source-discovery candidates. Layer title does not prove government authority, real deployment, or source accuracy. Human/public trust is never granted by discovering URLs.';
