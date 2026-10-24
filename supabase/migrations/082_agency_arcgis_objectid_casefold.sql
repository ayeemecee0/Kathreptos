-- 082: Existing production registration RPC must honor original ArcGIS case-sensitive field names such as lowercase `objectid` while binding the typed field to OBJECTID semantically.
create or replace function public.register_first_party_agency_flock_source(
 p_source_key text,p_page_sha256 text,p_layer_sha256 text,
 p_layer_name text,p_camera_id_field text,p_identity_basis text,
 p_locations jsonb
) returns boolean language plpgsql security definer set search_path=''
as $agency_first_party$
declare
  candidate public.flock_gis_source_candidates%rowtype;
  entry jsonb;
  lat double precision;
  lon double precision;
  identity int;
  identifiers int[]:='{}';
  sou text:='https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0';
  page text:='https://growth-management.alachuacounty.us/GIS';
  portal text:='https://mapgenius.alachuacounty.us/';
  n int;
  south double precision:=90;
  north double precision:=-90;
  west double precision:=180;
  east double precision:=-180;
begin
  select * into candidate from public.flock_gis_source_candidates
  where gis_layer_url=sou and trust_status='unverified';

  if p_source_key<>'agency_alachua_fl'
     or candidate.gis_layer_url is null
     or candidate.geometry_type<>'esriGeometryPoint'
     or lower(candidate.object_id_field)<>'objectid'
     or candidate.layer_name<>p_layer_name
     or p_layer_name !~* '^flock[_ ]cameras$'
     or candidate.public_gov_context_url<>page
     or lower(p_camera_id_field) not in ('objectid','cameraid','camera_id','name','id','camerano','cameranumber')
     or p_identity_basis not in ('arcgis_typed_objectid','named_camera_id')
     or (p_identity_basis='arcgis_typed_objectid' and lower(p_camera_id_field)<>'objectid')
     or (p_identity_basis='named_camera_id' and lower(p_camera_id_field)='objectid')
     or p_page_sha256 !~ '^[a-f0-9]{64}$'
     or p_layer_sha256 !~ '^[a-f0-9]{64}$'
     or exists(select 1 from public.trusted_flock_gis_sources
        where source_key=p_source_key or gis_layer_url=sou)
     or exists(select 1 from public.gis_government_host_authorities
        where authority_key=p_source_key)
  then
    raise exception 'First-party agency GIS evidence not independently attributable to the pinned government publisher';
  end if;

  if jsonb_typeof(p_locations)<>'array' then
    raise exception 'Original full first-party GIS inventory missing';
  end if;
  n:=jsonb_array_length(p_locations);
  if n not between 1 and 250 then
    raise exception 'First-party agency GIS camera count unsupported';
  end if;
  for entry in select value from jsonb_array_elements(p_locations)
  loop
    if jsonb_typeof(entry)<>'object'
       or jsonb_typeof(entry->'id')<>'number'
       or jsonb_typeof(entry->'lat')<>'number'
       or jsonb_typeof(entry->'lon')<>'number'
       or entry->>'id' !~ '^[0-9]{1,10}$'
    then raise exception 'Missing typed individual ArcGIS camera feature ID'; end if;
    identity:=(entry->>'id')::integer;
    lat:=(entry->>'lat')::double precision;
    lon:=(entry->>'lon')::double precision;
    -- Broad defensive Alachua County-area envelope. The exact geometry is
    -- exclusively the returned source GIS point, never this envelope.
    if identity<=0 or identity=any(identifiers)
       or not (lat between 29.0 and 30.4)
       or not (lon between -83.5 and -81.9)
    then raise exception 'Camera outside independently constrained county envelope or duplicate object ID';end if;
    if exists(select 1 from public.flock_camera_locations c
      where c.verification_status='verified' and c.location_accuracy='exact'
        and abs(c.latitude-lat)<0.0009
        and abs(c.longitude-lon)*cos(radians(lat))<0.0009) then
      raise exception 'Potential existing verified camera within 100 m; do not duplicate government records';
    end if;
    identifiers:=array_append(identifiers,identity);
    south:=least(south,lat);
    north:=greatest(north,lat);
    west:=least(west,lon);
    east:=greatest(east,lon);
  end loop;
  -- No impossibly wide source bounds or unsupported USA coordinate ranges.
  if north-south>1.4 or east-west>1.6
     or south-0.03<29 or north+0.03>30.4
     or west-0.03< -83.5 or east+0.03> -81.9 then
    raise exception 'County GIS point geometry extent requires further verification';
  end if;

  insert into public.gis_government_host_authorities(
    authority_key,government_gis_host,official_government_page,
    jurisdiction_label,allowed_layer_path,expected_layer_name,
    bounds_south,bounds_west,bounds_north,bounds_east,
    verification_status,independently_reviewed_at,trust_explanation)
  values (
    p_source_key,'maps.alachuacounty.us',page,'Alachua County, FL',
    '/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0',p_layer_name,
    south-0.03,west-0.03,north+0.03,east+0.03,
    'verified',now(),
    'Independent government-hosted GIS authority: original Alachua County GIS homepage controls linked agency map portal at the same registrable government domain, and county-operated ArcGIS server independently lists the exact Flock camera point layer, stable twice-read IDs, consistent geometry, original page and point fingerprints. No exact Flock layer backlink is required; operating status is unverified.'
  );
  insert into public.trusted_flock_gis_sources (
    source_key,gis_layer_url,government_evidence_url,
    jurisdiction_label,expected_camera_type_field,expected_id_field,
    bounds_south,bounds_west,bounds_north,bounds_east,
    source_status,review_basis,reviewed_at
  ) values (
    p_source_key,sou,page,'Alachua County, FL','FlockLayer','OBJECTID',
    south-0.03,west-0.03,north+0.03,east+0.03,
    'verified','Automatic first-party county GIS verification, independent of exact webpage-to-camera-layer hyperlink; 2-pass original complete object-ID list, individual georeferenced original Flock layer points and full duplicate checks. Does not establish uptime.',now()
  );
  insert into public.gis_verification_profiles (
    source_key,expected_layer_name,identity_mode,vendor_field,
    camera_id_field,service_evidence_mode,profile_status,review_basis
  ) values(
    p_source_key,p_layer_name,'official_flock_layer',null,
    p_camera_id_field,'listed_flock_layer','verified',
    'First-party authenticated Alachua County GIS service. Government domain/portal original-page publisher evidence and every georeferenced typed original ArcGIS camera record independently checked; no active camera operation claim.'
  );
  insert into public.first_party_agency_gis_receipts(
    source_key,agency_page_url,agency_portal_url,original_page_sha256,
    full_layer_points_sha256,original_camera_count,identity_basis)
  values(p_source_key,page,portal,p_page_sha256,p_layer_sha256,n,p_identity_basis);
  return true;
end
$agency_first_party$;

revoke all on function public.register_first_party_agency_flock_source(
 text,text,text,text,text,text,jsonb) from public,anon,authenticated,service_role;
grant execute on function public.register_first_party_agency_flock_source(
 text,text,text,text,text,text,jsonb) to service_role;

comment on function public.register_first_party_agency_flock_source(text,text,text,text,text,text,jsonb) is
'Owner-approved, source-pinned alternate first-party GIS verification path. An exact camera-layer backlink is not required if original agency controls GIS domain and live Flock layer/points are independently confirmed. Service role only; never call without full two-pass original audit.';
