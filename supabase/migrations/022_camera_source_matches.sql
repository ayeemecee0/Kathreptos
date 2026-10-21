-- 022: source-independent public-GIS/OSM matches. These never create or
-- approve public cameras; they attach corroboration to ALREADY verified GIS.
create table if not exists public.flock_camera_source_matches (
  candidate_key text not null references public.flock_camera_discovery_candidates(candidate_key),
  verified_camera_key text not null references public.flock_camera_locations(record_key),
  matching_method text not null default 'trusted_gis_to_osm_30m_v1'
    check(matching_method='trusted_gis_to_osm_30m_v1'),
  distance_m double precision not null check(distance_m between 0 and 30),
  first_matched_at timestamptz not null default now(),
  primary key(candidate_key,verified_camera_key)
);
create index if not exists camera_matches_official_idx
 on public.flock_camera_source_matches(verified_camera_key);

create or replace function public.check_independent_camera_match()
returns trigger language plpgsql security definer set search_path=''
as $match$
declare
  c public.flock_camera_discovery_candidates%rowtype;
  v public.flock_camera_locations%rowtype;
  dist double precision;
begin
  select * into c from public.flock_camera_discovery_candidates
    where candidate_key=new.candidate_key;
  select * into v from public.flock_camera_locations
    where record_key=new.verified_camera_key;

  if c.candidate_key is null or v.record_key is null
    or c.source_kind <> 'osm_public_dataset'
    or c.candidate_status <> 'unverified'
    or v.source_type <> 'official_government'
    or v.verification_method <> 'official_georeferenced_camera_record_v1'
    or v.verification_status <> 'verified'
    or not public.gis_camera_authority_current(v.source_url,v.jurisdiction_label)
    or new.matching_method <> 'trusted_gis_to_osm_30m_v1'
  then
    raise exception 'Camera corroboration requires independent OSM observation and currently verified government GIS source';
  end if;
  dist := 6371000.0 * 2.0 * asin(least(1.0,sqrt(
    power(sin(radians(c.latitude-v.latitude)/2.0),2)
    + cos(radians(c.latitude))*cos(radians(v.latitude))
      * power(sin(radians(c.longitude-v.longitude)/2.0),2)
  )));
  if dist > 30 then
    raise exception 'Community location too far from independently verified official camera';
  end if;
  new.distance_m := dist; -- calculated in database, not accepted from worker
  return new;
end;
$match$;

drop trigger if exists guard_independent_camera_match
 on public.flock_camera_source_matches;
create trigger guard_independent_camera_match before insert
on public.flock_camera_source_matches for each row
execute function public.check_independent_camera_match();

alter table public.flock_camera_source_matches enable row level security;
revoke all on public.flock_camera_source_matches from anon,authenticated,service_role;
grant select,insert on public.flock_camera_source_matches to service_role;
comment on table public.flock_camera_source_matches is
'Private immutable spatial correlation of independent OSM node to verified official GIS camera. This never publishes or adds a camera and may not be counted as an independently verified new placement.';
