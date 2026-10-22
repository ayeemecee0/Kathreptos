-- 023: automatic promotion of independently authorized governmental GIS layers.
-- Trust is rooted in an owner-controlled, immutable government host binding.
-- Discovery alone (third-party ArcGIS, OSM, or a page mentioning Flock) cannot
-- grant authority. Only one exact government-hosted Sheriff layer is eligible.

create table if not exists public.gis_government_host_authorities (
  authority_key text primary key check(authority_key ~ '^[a-z0-9_]{5,50}$'),
  government_gis_host text not null unique check (government_gis_host ~ '^[a-z0-9.-]+$'),
  official_government_page text not null check (official_government_page ~ '^https://[a-z0-9.-]+/'),
  jurisdiction_label text not null check (length(jurisdiction_label) between 5 and 150),
  allowed_layer_path text not null check (allowed_layer_path ~ '^/[a-zA-Z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'),
  expected_layer_name text not null check (expected_layer_name ~ '^Flock[_ ]Cameras$'),
  bounds_south double precision not null,
  bounds_west double precision not null,
  bounds_north double precision not null,
  bounds_east double precision not null,
  verification_status text not null check(verification_status in ('verified','revoked')),
  independently_reviewed_at timestamptz not null,
  trust_explanation text not null check(length(trust_explanation) between 70 and 1400),
  check (bounds_south between 17 and 72 and bounds_north between 17 and 72
    and bounds_west between -180 and -64 and bounds_east between -180 and -64
    and bounds_south < bounds_north and bounds_west < bounds_east)
);

alter table public.gis_government_host_authorities enable row level security;
revoke all on public.gis_government_host_authorities from anon, authenticated, service_role;
grant select on public.gis_government_host_authorities to service_role;

insert into public.gis_government_host_authorities (
  authority_key,government_gis_host,official_government_page,jurisdiction_label,
  allowed_layer_path,expected_layer_name,
  bounds_south,bounds_west,bounds_north,bounds_east,
  verification_status,independently_reviewed_at,trust_explanation
) values (
  'elpaso_co','gisservices.elpasoco.com',
  'https://admin.elpasoco.com/digital-strategy-and-technology/licensed-gis-data/',
  'El Paso County, CO',
  '/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer/1',
  'Flock_Cameras',
  38.55,-105.3,39.25,-104.3,
  'verified',now(),
  'Independently examined county-operated GIS host under El Paso County government domain. The exact Sheriff MapServer advertises an Flock camera map and a point feature layer Flock_Cameras. The county GIS department publishes its GIS operations on an official government-controlled page. This does not prove devices online.'
) on conflict(authority_key) do nothing;

-- The publicly documented government GIS layer is initially a candidate.
-- Only the validator may request promotion through the restricted function.
insert into public.trusted_flock_gis_sources(
 source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
 expected_camera_type_field,expected_id_field,
 bounds_south,bounds_west,bounds_north,bounds_east,source_status,review_basis
) values (
 'elpaso_co',
 'https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer/1',
 'https://admin.elpasoco.com/digital-strategy-and-technology/licensed-gis-data/',
 'El Paso County, CO','FlockLayer','OBJECTID',
 38.55,-105.3,39.25,-104.3,'candidate',
 'Government GIS host independently bound to El Paso County. Approval requires fresh exact Sheriff MapServer and Flock_Cameras feature metadata validation, live positive inventory and immutable proof receipt.'
) on conflict(source_key) do nothing;

create table if not exists public.official_gis_authority_receipts (
  source_key text primary key references public.trusted_flock_gis_sources(source_key),
  layer_metadata_sha256 text not null check(layer_metadata_sha256 ~ '^[0-9a-f]{64}$'),
  service_metadata_sha256 text not null check(service_metadata_sha256 ~ '^[0-9a-f]{64}$'),
  verified_at timestamptz not null default now(),
  verification_method text not null default 'owner_bound_official_sheriff_gis_metadata_v1'
    check (verification_method='owner_bound_official_sheriff_gis_metadata_v1')
);
alter table public.official_gis_authority_receipts enable row level security;
revoke all on public.official_gis_authority_receipts from anon,authenticated,service_role;
grant select on public.official_gis_authority_receipts to service_role;

create or replace function public.promote_owner_bound_gis_source(
 p_source_key text,p_layer_sha text,p_service_sha text
) returns boolean
language plpgsql security definer set search_path=''
as $promote_gis$
declare
  s public.trusted_flock_gis_sources%rowtype;
  a public.gis_government_host_authorities%rowtype;
begin
  select * into s from public.trusted_flock_gis_sources where source_key=p_source_key for update;
  select * into a from public.gis_government_host_authorities where authority_key=p_source_key;
  if s.source_key is null or a.authority_key is null
    or a.verification_status <> 'verified'
    or s.source_status <> 'candidate'
    or s.gis_layer_url <> 'https://' || a.government_gis_host || a.allowed_layer_path
    or s.government_evidence_url <> a.official_government_page
    or s.jurisdiction_label <> a.jurisdiction_label
    or s.expected_camera_type_field <> 'FlockLayer'
    or s.expected_id_field <> 'OBJECTID'
    or (s.bounds_south,s.bounds_west,s.bounds_north,s.bounds_east)
       is distinct from
       (a.bounds_south,a.bounds_west,a.bounds_north,a.bounds_east)
    or p_layer_sha !~ '^[0-9a-f]{64}$'
    or p_service_sha !~ '^[0-9a-f]{64}$'
  then
    raise exception 'Source authority is not anchored to a reviewed government GIS host';
  end if;
  update public.trusted_flock_gis_sources
  set source_status='verified',reviewed_at=now(),
      review_basis='Automated owner-bound GIS validation: exact Sheriff Flock_Cameras point layer, Flock Safety service metadata, county authority and positive bounded GIS inventory.'
  where source_key=p_source_key;
  insert into public.official_gis_authority_receipts(source_key,layer_metadata_sha256,service_metadata_sha256)
    values(p_source_key,p_layer_sha,p_service_sha);
  return true;
end;
$promote_gis$;
revoke all on function public.promote_owner_bound_gis_source(text,text,text) from public;
grant execute on function public.promote_owner_bound_gis_source(text,text,text) to service_role;

create or replace function public.revoke_gis_after_host_authority_revocation()
returns trigger language plpgsql security definer set search_path=''
as $revoked_gis_host$
begin
 if old.verification_status='verified' and new.verification_status <> 'verified' then
   update public.trusted_flock_gis_sources set source_status='revoked'
   where source_key=old.authority_key and source_status='verified';
 end if;
 return new;
end;
$revoked_gis_host$;
drop trigger if exists revoke_gis_after_host_authority_revocation
  on public.gis_government_host_authorities;
create trigger revoke_gis_after_host_authority_revocation
after update of verification_status on public.gis_government_host_authorities
for each row execute function public.revoke_gis_after_host_authority_revocation();

comment on table public.gis_government_host_authorities is
'Owner-reviewed root government GIS host and exact eligible layer, allowing unattended revalidation but never service-role origin approvals.';
