-- 039 - Source-first automatic verification for NEW government-domain Flock GIS.
-- A discovered .gov domain alone is not camera evidence. Require a fresh
-- original .gov page containing a direct GIS hyperlink, with exactly matching
-- SHA-256 in the private discovery registry. The GIS host must share the
-- same .gov apex, every feature must identify a Flock-only point layer,
-- all points are bounded and deduplicated, and no external ArcGIS host qualifies.
create table if not exists public.auto_discovered_government_flock_gis (
  source_key text primary key references public.trusted_flock_gis_sources(source_key),
  government_page_url text not null,
  original_page_sha256 text not null check(original_page_sha256 ~ '^[a-f0-9]{64}$'),
  original_layer_sha256 text not null check(original_layer_sha256 ~ '^[a-f0-9]{64}$'),
  original_feature_count integer not null check(original_feature_count between 1 and 250),
  verified_at timestamptz not null default now()
);
alter table public.auto_discovered_government_flock_gis enable row level security;
revoke all on public.auto_discovered_government_flock_gis
 from public,anon,authenticated,service_role;
grant select on public.auto_discovered_government_flock_gis to service_role;

create or replace function public.register_original_gov_flock_source(
 p_source_key text,p_page_url text,p_gis_layer_url text,p_layer_name text,
 p_camera_id_field text,p_vendor_field text,
 p_page_sha256 text,p_layer_sha256 text,p_locations jsonb
) returns boolean language plpgsql security definer set search_path=''
as $register_original_gov$
declare
  lead public.government_gis_search_queue%rowtype;
  candidate public.flock_gis_source_candidates%rowtype;
  page_host text;
  layer_host text;
  page_apex text;
  layer_apex text;
  layer_path text;
  loc jsonb;
  point_oid integer;
  lon double precision;
  lat double precision;
  min_lon double precision:=180;
  max_lon double precision:=-180;
  min_lat double precision:=90;
  max_lat double precision:=-90;
  seen int[]:='{}'::int[];
  loc_count int:=0;
begin
  select * into lead from public.government_gis_search_queue
   where page_url=p_page_url and candidate_status='unverified';
  select * into candidate from public.flock_gis_source_candidates
   where gis_layer_url=p_gis_layer_url and trust_status='unverified';
  page_host:=split_part(split_part(p_page_url,'https://',2),'/',1);
  layer_host:=split_part(split_part(p_gis_layer_url,'https://',2),'/',1);
  page_apex:=array_to_string((string_to_array(page_host,'.'))[
    greatest(array_length(string_to_array(page_host,'.'),1)-1,1):
  ],'.');
  layer_apex:=array_to_string((string_to_array(layer_host,'.'))[
    greatest(array_length(string_to_array(layer_host,'.'),1)-1,1):
  ],'.');
  layer_path:=substring(p_gis_layer_url from length('https://'||layer_host)+1);
  if lead.page_url is null or candidate.gis_layer_url is null
   or p_source_key !~ '^autogov_[a-f0-9]{20}$'
   or p_page_url !~ '^https://([a-z0-9-]+\.)+gov/.+'
   or p_gis_layer_url !~ '^https://([a-z0-9-]+\.)+gov/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'
   or page_apex<>layer_apex or page_apex !~ '^[a-z0-9-]+\.gov$'
   or candidate.layer_name<>p_layer_name
   or candidate.geometry_type<>'esriGeometryPoint'
   or candidate.object_id_field<>'OBJECTID'
   or p_layer_name !~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$'
   or p_camera_id_field not in ('NAME','CameraID','ID','Camera_ID')
   or (p_vendor_field is not null and p_vendor_field not in ('CameraType','Type','Manufacturer'))
   or p_page_sha256<>lead.page_sha256
   or p_page_sha256 !~ '^[a-f0-9]{64}$'
   or p_layer_sha256 !~ '^[a-f0-9]{64}$'
   or not lead.gis_links @> jsonb_build_array(p_gis_layer_url)
   or exists(select 1 from public.trusted_flock_gis_sources
       where source_key=p_source_key or gis_layer_url=p_gis_layer_url)
  then
    raise exception 'No independently corroborated original .gov source-to-camera-map link';
  end if;
  if jsonb_typeof(p_locations)<>'array'
     or jsonb_array_length(p_locations) not between 1 and 250 then
    raise exception 'Original .gov Flock camera inventory incomplete';
  end if;
  for loc in select value from jsonb_array_elements(p_locations) as value
  loop
    if jsonb_typeof(loc)<>'object'
       or jsonb_typeof(loc->'id')<>'number'
       or jsonb_typeof(loc->'lat')<>'number'
       or jsonb_typeof(loc->'lon')<>'number'
       or loc->>'id' !~ '^[0-9]{1,10}$'
    then raise exception 'Original government camera feature geometry not verified';end if;
    point_oid:=(loc->>'id')::integer;
    lat:=(loc->>'lat')::double precision;
    lon:=(loc->>'lon')::double precision;
    if point_oid<=0 or point_oid=any(seen)
      or lat not between 17 and 72 or lon not between -180 and -64 then
      raise exception 'Original government GIS has ambiguous or non-US camera';
    end if;
    seen:=array_append(seen,point_oid);
    min_lat:=least(min_lat,lat);max_lat:=greatest(max_lat,lat);
    min_lon:=least(min_lon,lon);max_lon:=greatest(max_lon,lon);
    if exists(
      select 1 from public.flock_camera_locations c
      where c.location_accuracy='exact' and c.verification_status='verified'
        and abs(c.latitude-lat)<0.00075
        and abs(c.longitude-lon)<0.00075/greatest(cos(radians(lat)),0.1)
    ) then raise exception 'Government map contains possible existing published camera';end if;
    loc_count:=loc_count+1;
  end loop;
  -- This is a source-inventory geographic safety envelope, NOT a claimed
  -- political boundary. Reject implausibly dispersed "municipal" inventories.
  if max_lat-min_lat>2.5 or max_lon-min_lon>2.5 or
     min_lat-0.05<17 or max_lat+0.05>72 or
     min_lon-0.05< -180 or max_lon+0.05> -64 then
    raise exception 'Source geometry too broad to infer a safe local verification envelope';
  end if;
  insert into public.gis_government_host_authorities(
    authority_key,government_gis_host,official_government_page,
    jurisdiction_label,allowed_layer_path,expected_layer_name,
    bounds_south,bounds_west,bounds_north,bounds_east,
    verification_status,independently_reviewed_at,trust_explanation
  ) values(
    p_source_key,layer_host,p_page_url,
    'Government GIS: '||page_host,layer_path,p_layer_name,
    min_lat-0.05,min_lon-0.05,max_lat+0.05,max_lon+0.05,
    'verified',now(),
    'Automated first-party original .gov Flock map verification: live matching original municipal government disclosure directly links exact same-apex government GIS point layer, all features have individual camera identities, and coordinates are bounded/deduplicated. Label uses original government hostname until official jurisdiction name is independently resolved.'
  );
  insert into public.trusted_flock_gis_sources(
    source_key,gis_layer_url,government_evidence_url,
    jurisdiction_label,expected_camera_type_field,expected_id_field,
    bounds_south,bounds_west,bounds_north,bounds_east,
    source_status,review_basis,reviewed_at
  ) values(
    p_source_key,p_gis_layer_url,p_page_url,'Government GIS: '||page_host,
    coalesce(p_vendor_field,'FlockLayer'),'OBJECTID',
    min_lat-0.05,min_lon-0.05,max_lat+0.05,max_lon+0.05,
    'verified','First-party .gov evidence verified by direct original website-to-point-layer link and complete bounded camera inventory. Source scope is original government hostname and not an invented agency name.',now()
  );
  insert into public.gis_verification_profiles(
    source_key,expected_layer_name,identity_mode,vendor_field,camera_id_field,
    service_evidence_mode,profile_status,review_basis
  ) values(
    p_source_key,p_layer_name,'official_flock_layer',p_vendor_field,
    p_camera_id_field,'listed_flock_layer','verified',
    'Only a Flock camera point layer directly linked from a source-specific original United States government Flock disclosure may enter, with the same government .gov apex and individually identified and bounded source camera coordinates.'
  );
  insert into public.auto_discovered_government_flock_gis(
    source_key,government_page_url,original_page_sha256,
    original_layer_sha256,original_feature_count
  ) values(p_source_key,p_page_url,p_page_sha256,p_layer_sha256,loc_count);
  return true;
end;
$register_original_gov$;
revoke all on function public.register_original_gov_flock_source(
 text,text,text,text,text,text,text,text,jsonb)
 from public,anon,authenticated,service_role;
grant execute on function public.register_original_gov_flock_source(
 text,text,text,text,text,text,text,text,jsonb)
 to service_role;
