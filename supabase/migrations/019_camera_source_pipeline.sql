-- Katoptron v019: trusted GIS source bindings + private, deduplicated discovery queue.
-- Data source candidates never become public camera pins merely through ingestion.
-- Only DB-owner reviewed source bindings can be used for unattended official GIS
-- publication. The service role cannot approve new government GIS endpoints.
create table if not exists public.trusted_flock_gis_sources (
  source_key text primary key check (source_key ~ '^[a-z0-9_-]{4,50}$'),
  gis_layer_url text not null unique check (
    gis_layer_url ~ '^https://[a-z0-9.-]+/.*(FeatureServer|MapServer)/[0-9]+$'),
  government_evidence_url text not null check (
    government_evidence_url ~ '^https://[a-z0-9.-]+/'),
  jurisdiction_label text not null check (length(btrim(jurisdiction_label)) between 5 and 150),
  expected_camera_type_field text not null check (expected_camera_type_field ~ '^[A-Za-z][A-Za-z0-9_]{1,40}$'),
  expected_id_field text not null check (expected_id_field ~ '^[A-Za-z][A-Za-z0-9_]{1,40}$'),
  bounds_south double precision not null,
  bounds_west double precision not null,
  bounds_north double precision not null,
  bounds_east double precision not null,
  source_status text not null default 'candidate' check(source_status in('candidate','verified','revoked')),
  review_basis text not null check (length(btrim(review_basis)) between 30 and 900),
  reviewed_at timestamptz,
  check(bounds_south between 17 and 72 and bounds_north between 17 and 72
    and bounds_south < bounds_north and bounds_west between -180 and -64
    and bounds_east between -180 and -64 and bounds_west < bounds_east),
  check(source_status <> 'verified' or reviewed_at is not null)
);

alter table public.trusted_flock_gis_sources enable row level security;
revoke all on public.trusted_flock_gis_sources from anon,authenticated,service_role;
grant select on public.trusted_flock_gis_sources to service_role;

-- Independently inspected authority: Monroe's city ALPR program points to the
-- municipality-operated GIS Utility Map → Camera Systems. The precise GIS
-- layer has CameraType and point coordinates. Only rows with an EXPLICIT
-- Flock camera type pass the independent publication code.
insert into public.trusted_flock_gis_sources
(source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
 expected_camera_type_field,expected_id_field,
 bounds_south,bounds_west,bounds_north,bounds_east,
 source_status,review_basis,reviewed_at)
values
('monroe_wa',
 'https://gis.monroewa.gov/citygis/rest/services/UtilityData/Street_Layers/MapServer/22',
 'https://monroewa.gov/1324/Flock-Safety-Camera-Program',
 'Monroe, WA','CameraType','OBJECTID',
 47.80,-122.12,48.00,-121.80,'verified',
 'Official Monroe Flock program explicitly links the city GIS Utility Map Camera Systems layer. GIS REST Camera Systems layer 22 is municipal and contains CameraType and point coordinates; require exact manufacturer designation per row.',now())
on conflict(source_key) do nothing;

create table if not exists public.flock_camera_discovery_candidates (
  candidate_key text primary key check (candidate_key ~ '^[a-z0-9:_-]{7,180}$'),
  source_kind text not null check (source_kind in
    ('osm_public_dataset','community_report','official_gis_unclassified')),
  source_url text not null check (
    source_url ~ '^https://[A-Za-z0-9.-]+(/|$)' and length(source_url) <= 2048),
  source_external_id text not null check (length(source_external_id) between 1 and 100),
  latitude double precision not null check(latitude between 17 and 72),
  longitude double precision not null check(longitude between -180 and -64),
  declared_vendor text not null check(length(btrim(declared_vendor)) between 4 and 120),
  evidence_excerpt text not null check(length(btrim(evidence_excerpt)) between 15 and 700),
  evidence_fingerprint text not null check(evidence_fingerprint ~ '^[0-9a-f]{64}$'),
  discovered_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  candidate_status text not null default 'unverified'
    check (candidate_status in ('unverified','rejected','superseded')),
  check(last_seen_at >= discovered_at)
);
create index if not exists flock_camera_candidates_location_idx
 on public.flock_camera_discovery_candidates(latitude,longitude);
create index if not exists flock_camera_candidates_recent_idx
 on public.flock_camera_discovery_candidates(last_seen_at desc);
alter table public.flock_camera_discovery_candidates enable row level security;
revoke all on public.flock_camera_discovery_candidates from anon,authenticated,service_role;
grant select,insert on public.flock_camera_discovery_candidates to service_role;
grant update(last_seen_at) on public.flock_camera_discovery_candidates to service_role;

-- A GIS source can be revoked by the owner. The camera verifier respects the
-- owner trust record and independently checks the live official government URL.
-- No community candidate or news search can approve trust automatically.

comment on table public.trusted_flock_gis_sources is
'Database-owner approved exact official GIS sources. Discovery workers may read but cannot approve or alter trust.';
comment on table public.flock_camera_discovery_candidates is
'Private raw OSM/community/ambiguous camera reports. Never eligible for public disclosure from this table alone, and no implicit vendor verification.';
