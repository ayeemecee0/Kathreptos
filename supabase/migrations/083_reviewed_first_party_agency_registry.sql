-- 083: Reviewed first-party government GIS sources no longer require one SQL
-- function per agency. The source registry is controlled by DB migrations /
-- owner-authorized review. GitHub service worker has SELECT only; neither
-- anonymous, contributor nor service role can approve NEW authority roots.
create table if not exists public.reviewed_first_party_gis_roots (
 source_key text primary key check(source_key ~ '^agency_[a-z0-9_]{5,46}$'),
 agency_page_url text not null check (agency_page_url ~ '^https://[a-z0-9.-]+/'),
 agency_portal_url text not null check (agency_portal_url ~ '^https://[a-z0-9.-]+/'),
 gis_layer_url text not null unique check
  (gis_layer_url ~ '^https://[a-z0-9.-]+/[A-Za-z0-9_/-]+/(FeatureServer|MapServer)/[0-9]+$'),
 jurisdiction_label text not null check(length(jurisdiction_label) between 5 and 150),
 bounds_south double precision not null,
 bounds_west double precision not null,
 bounds_north double precision not null,
 bounds_east double precision not null,
 review_basis text not null check(length(btrim(review_basis)) between 130 and 2000),
 reviewed_at timestamptz not null,
 review_status text not null check (review_status in ('verified','revoked')),
 constraint first_party_reviewed_bounds check (
   bounds_south>=17 and bounds_south<bounds_north and bounds_north<=72
   and bounds_west>=-180 and bounds_west<bounds_east and bounds_east<=-64
   and bounds_north-bounds_south<=2.5 and bounds_east-bounds_west<=2.5)
);
alter table public.reviewed_first_party_gis_roots enable row level security;
revoke all on public.reviewed_first_party_gis_roots from public,anon,authenticated,service_role;
grant select on public.reviewed_first_party_gis_roots to service_role;

-- This is a transcription of an existing independently verified and published
-- original Alachua source. Do not auto-import generic Esri catalog hits.
insert into public.reviewed_first_party_gis_roots (
 source_key,agency_page_url,agency_portal_url,gis_layer_url,
 jurisdiction_label,bounds_south,bounds_west,bounds_north,bounds_east,
 review_basis,reviewed_at,review_status)
values (
 'agency_alachua_fl','https://growth-management.alachuacounty.us/GIS',
 'https://mapgenius.alachuacounty.us/',
 'https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0',
 'Alachua County, FL',29.0,-83.5,30.4,-81.9,
 'Reviewed original Alachua County government GIS homepage links an agency-operated public mapping portal on the same authenticated county domain. The original government-operated ArcGIS feature layer identifies Flock Cameras and provides 18 complete distinct point-feature ObjectIDs verified twice. Government-published positions, not operational status.',
 now(),'verified'
) on conflict (source_key) do nothing;

create or replace function public.register_reviewed_first_party_flock_source(
 p_source_key text,p_page_sha256 text,p_layer_sha256 text,
 p_layer_name text,p_camera_id_field text,p_identity_basis text,p_locations jsonb
) returns boolean language plpgsql security definer set search_path=''
as $agency_registry$
declare
  approved public.reviewed_first_party_gis_roots%rowtype;
  candidate public.flock_gis_source_candidates%rowtype;
  layer_host text;
  layer_path text;
  value jsonb;
  fid integer;
  lat double precision;
  lon double precision;
  seen integer[]:='{}';
  n integer;
begin
  select * into approved from public.reviewed_first_party_gis_roots
   where source_key=p_source_key and review_status='verified' and reviewed_at is not null;
  if approved.source_key is null
     or p_page_sha256 !~ '^[a-f0-9]{64}$'
     or p_layer_sha256 !~ '^[a-f0-9]{64}$'
     or p_layer_name !~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$'
     or p_camera_id_field !~ '^[A-Za-z][A-Za-z0-9_]{1,50}$'
     or p_identity_basis not in ('arcgis_typed_objectid','named_camera_id')
  then
    raise exception 'No independently reviewed original agency GIS source';
  end if;
  select * into candidate from public.flock_gis_source_candidates
   where gis_layer_url=approved.gis_layer_url and trust_status='unverified';
  if candidate.gis_layer_url is null
     or candidate.public_gov_context_url<>approved.agency_page_url
     or candidate.layer_name<>p_layer_name
     or candidate.geometry_type<>'esriGeometryPoint'
     or candidate.object_id_field !~* '^objectid(_[0-9]+)?$'
     or (p_identity_basis='arcgis_typed_objectid' and
         lower(p_camera_id_field)<>lower(candidate.object_id_field))
     or (p_identity_basis='named_camera_id' and
         lower(p_camera_id_field)=lower(candidate.object_id_field))
     or exists(select 1 from public.trusted_flock_gis_sources
       where source_key=p_source_key or gis_layer_url=approved.gis_layer_url)
     or exists(select 1 from public.gis_government_host_authorities
       where authority_key=p_source_key)
  then
    raise exception 'Reviewed agency binding does not match exact private GIS candidate';
  end if;

  layer_host:=split_part(split_part(approved.gis_layer_url,'https://',2),'/',1);
  layer_path:=substring(approved.gis_layer_url from length('https://'||layer_host)+1);
  if layer_host !~ '^[a-z0-9.-]+$'
     or layer_path !~ '^/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'
     or layer_host not like '%.%'
     or split_part(layer_host,'.',1) in ('localhost','127')
  then raise exception 'Reviewed government GIS layer URL invalid';end if;

  if jsonb_typeof(p_locations)<>'array' then
    raise exception 'Complete original agency point inventory required';
  end if;
  n:=jsonb_array_length(p_locations);
  if n not between 1 and 250 then
    raise exception 'Original agency point inventory empty or truncated';
  end if;
  for value in select x.value from jsonb_array_elements(p_locations) as x(value)
  loop
    if jsonb_typeof(value)<>'object'
      or jsonb_typeof(value->'id')<>'number'
      or jsonb_typeof(value->'lat')<>'number'
      or jsonb_typeof(value->'lon')<>'number'
      or value->>'id' !~ '^[0-9]{1,10}$'
    then raise exception 'Original agency point ID or coordinates malformed';end if;
    fid:=(value->>'id')::integer;
    lat:=(value->>'lat')::double precision;
    lon:=(value->>'lon')::double precision;
    if fid<=0 or fid=any(seen)
       or lat not between approved.bounds_south and approved.bounds_north
       or lon not between approved.bounds_west and approved.bounds_east
    then raise exception 'Outside reviewed agency GIS geographic bounds or repeated feature';end if;
    if exists(select 1 from public.flock_camera_locations c
      where c.verification_status='verified' and c.location_accuracy='exact'
        and abs(c.latitude-lat)<0.0009
        and abs(c.longitude-lon)*cos(radians(lat))<0.0009)
    then raise exception 'Possible existing verified camera; do not duplicate government locations';end if;
    seen:=array_append(seen,fid);
  end loop;

  insert into public.gis_government_host_authorities (
    authority_key,government_gis_host,official_government_page,
    jurisdiction_label,allowed_layer_path,expected_layer_name,
    bounds_south,bounds_west,bounds_north,bounds_east,
    verification_status,independently_reviewed_at,trust_explanation)
  values (
    approved.source_key,layer_host,approved.agency_page_url,
    approved.jurisdiction_label,layer_path,p_layer_name,
    approved.bounds_south,approved.bounds_west,approved.bounds_north,approved.bounds_east,
    'verified',approved.reviewed_at,
    'Owner-reviewed first-party government GIS publisher and original agency map portal. Exact vetted government layer, double-checked complete original ArcGIS ObjectIDs, Flock-labelled points, SHA-256 source fingerprints, reviewed geographic envelope and existing-camera duplicate exclusions. No operational activity is claimed.'
  );
  insert into public.trusted_flock_gis_sources (
    source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
    expected_camera_type_field,expected_id_field,
    bounds_south,bounds_west,bounds_north,bounds_east,source_status,review_basis,reviewed_at)
  values (
    approved.source_key,approved.gis_layer_url,approved.agency_page_url,
    approved.jurisdiction_label,'FlockLayer',candidate.object_id_field,
    approved.bounds_south,approved.bounds_west,approved.bounds_north,approved.bounds_east,
    'verified',
    'Owner-approved county or city agency-operated GIS source with original government-owned server, original map-portal authentication, live complete object-ID inventory and separately checked exact Flock camera georeferenced features. No active-camera claim.',
    now()
  );
  insert into public.gis_verification_profiles (
    source_key,expected_layer_name,identity_mode,vendor_field,camera_id_field,
    service_evidence_mode,profile_status,review_basis)
  values (
    approved.source_key,p_layer_name,'official_flock_layer',null,p_camera_id_field,
    'listed_flock_layer','verified',
    'Owner-reviewed original government-hosted GIS agency source. Exact approved hostname and ArcGIS feature layer bound to original government map portal; complete double-checked feature identities and coordinates independently verified; no operation or plate detection claim.'
  );
  insert into public.first_party_agency_gis_receipts (
    source_key,agency_page_url,agency_portal_url,original_page_sha256,
    full_layer_points_sha256,original_camera_count,identity_basis)
  values (
    approved.source_key,approved.agency_page_url,approved.agency_portal_url,
    p_page_sha256,p_layer_sha256,n,p_identity_basis
  );
  return true;
end
$agency_registry$;

revoke all on function public.register_reviewed_first_party_flock_source(
 text,text,text,text,text,text,jsonb) from public,anon,authenticated,service_role;
grant execute on function public.register_reviewed_first_party_flock_source(
 text,text,text,text,text,text,jsonb) to service_role;

comment on function public.register_reviewed_first_party_flock_source(text,text,text,text,text,text,jsonb) is
'Approved original government GIS sources only; cannot add a new approval root. Service-role verifier must recheck live original agency webpage, GIS Flock layer, complete typed twice-read IDs and government georeferenced points. Returns false or errors before public camera publication.';
