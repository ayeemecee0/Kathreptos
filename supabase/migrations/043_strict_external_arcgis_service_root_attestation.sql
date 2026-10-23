-- 043: Endorsement via an original government hyperlink to a public ArcGIS
-- feature service ROOT (not just an individually numbered point layer).
-- A service-level link is weaker: only acceptable if exactly one unverified
-- Flock-named point layer exists under that service in the research registry,
-- and the live service metadata and ArcGIS government organization are
-- re-verified before a service-role-only source registration call.
alter table public.official_external_flock_gis_authorities
 add column if not exists government_link_method text not null
 default 'government_page_direct_anchor_v1'
 check(government_link_method in
   ('government_page_direct_anchor_v1','government_page_direct_service_v1'));

create or replace function public.confirm_original_government_linked_point_layer(
 p_parent_source_key text,p_disclosure_url text,p_layer_url text,
 p_page_sha256 text
) returns boolean language plpgsql security definer set search_path=''
as $gov_link_point$
declare
  parent public.trusted_flock_gis_sources%rowtype;
  root public.gis_government_host_authorities%rowtype;
  lead public.government_gis_disclosure_leads%rowtype;
  updated int;
begin
  select * into parent from public.trusted_flock_gis_sources
   where source_key=p_parent_source_key and source_status='verified';
  select * into root from public.gis_government_host_authorities
   where authority_key=p_parent_source_key and verification_status='verified';
  select * into lead from public.government_gis_disclosure_leads
   where disclosure_url=p_disclosure_url and gis_layer_url=p_layer_url;
  if parent.source_key is null or root.authority_key is null
   or lead.gis_layer_url is null
   or parent.gis_layer_url<>'https://' ||root.government_gis_host||root.allowed_layer_path
   or parent.government_evidence_url<>root.official_government_page
   or parent.jurisdiction_label<>root.jurisdiction_label
   or p_disclosure_url<>root.official_government_page
   or p_page_sha256 !~ '^[a-f0-9]{64}$'
   or lead.government_page_sha256<>p_page_sha256
   or lead.jurisdiction_label<>root.jurisdiction_label
   or lead.discovery_method not in ('government_page_direct_anchor_v1','government_page_direct_service_v1')
   or (lead.discovery_method='government_page_direct_service_v1'
       and (select count(*) from public.flock_gis_source_candidates c
            where c.trust_status='unverified'
              and c.geometry_type='esriGeometryPoint'
              and c.gis_layer_url like regexp_replace(p_layer_url,'/[0-9]+   or lead.layer_metadata_status not in ('unverified','point_layer_verified')
   or p_layer_url !~ '^https://services[0-9]*\.arcgis\.com/[A-Za-z0-9]+/arcgis/rest/services/[A-Za-z0-9_-]+/FeatureServer/[0-9]+$'
   or not exists(select 1 from public.flock_gis_source_candidates
       where gis_layer_url=p_layer_url and trust_status='unverified'
         and geometry_type='esriGeometryPoint'
         and layer_name ~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$')
  then
    raise exception 'Original-government Flock GIS hyperlink attestation failed';
  end if;
  update public.government_gis_disclosure_leads
   set layer_metadata_status='point_layer_verified',last_seen_at=now()
   where disclosure_url=p_disclosure_url and gis_layer_url=p_layer_url;
  get diagnostics updated=row_count;
  return updated=1;
end;
$gov_link_point$;

create or replace function public.register_official_external_flock_gis(
 p_parent_source_key text,p_source_key text,p_disclosure_url text,
 p_gis_layer_url text,p_layer_name text,p_camera_id_field text,
 p_vendor_field text,p_page_sha256 text,p_layer_sha256 text,
 p_org_id text,p_org_title text,p_locations jsonb
) returns boolean language plpgsql security definer set search_path=''
as $external_register$
declare
  parent public.trusted_flock_gis_sources%rowtype;
  root public.gis_government_host_authorities%rowtype;
  lead public.government_gis_disclosure_leads%rowtype;
  candidate public.flock_gis_source_candidates%rowtype;
  loc jsonb;
  point_oid integer;
  x double precision;
  y double precision;
  ids int[]:='{}'::int[];
  pts int:=0;
begin
  select * into parent from public.trusted_flock_gis_sources
   where source_key=p_parent_source_key and source_status='verified';
  select * into root from public.gis_government_host_authorities
   where authority_key=p_parent_source_key and verification_status='verified';
  select * into lead from public.government_gis_disclosure_leads
   where disclosure_url=p_disclosure_url and gis_layer_url=p_gis_layer_url
     and discovery_method in ('government_page_direct_anchor_v1','government_page_direct_service_v1')
     and layer_metadata_status='point_layer_verified';
  select * into candidate from public.flock_gis_source_candidates
   where gis_layer_url=p_gis_layer_url and trust_status='unverified';
  if parent.source_key is null or root.authority_key is null
   or lead.gis_layer_url is null or candidate.gis_layer_url is null
   or parent.gis_layer_url<>'https://' ||root.government_gis_host||root.allowed_layer_path
   or parent.government_evidence_url<>root.official_government_page
   or parent.jurisdiction_label<>root.jurisdiction_label
   or p_disclosure_url<>root.official_government_page
   or lead.source_host_scope<>split_part(split_part(p_disclosure_url,'https://',2),'/',1)
   or lead.jurisdiction_label<>parent.jurisdiction_label
   or lead.layer_host<>split_part(split_part(p_gis_layer_url,'https://',2),'/',1)
   or lead.government_page_sha256<>p_page_sha256
   or (lead.discovery_method='government_page_direct_service_v1'
       and (select count(*) from public.flock_gis_source_candidates c
            where c.trust_status='unverified'
              and c.geometry_type='esriGeometryPoint'
              and c.gis_layer_url like
                regexp_replace(p_gis_layer_url,'/[0-9]+
              and c.layer_name ~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?   or p_page_sha256 !~ '^[a-f0-9]{64}$'
   or p_layer_sha256 !~ '^[a-f0-9]{64}$'
   or p_source_key !~ '^ext_[a-z0-9_]{8,45}$'
   or p_layer_name<>candidate.layer_name
   or p_layer_name !~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$'
   or candidate.geometry_type<>'esriGeometryPoint'
   or candidate.object_id_field<>'OBJECTID'
   or p_camera_id_field not in ('NAME','CameraID','ID','Camera_ID')
   or (p_vendor_field is not null and p_vendor_field not in ('CameraType','Type','Manufacturer'))
   or p_gis_layer_url !~ '^https://services[0-9]*\.arcgis\.com/[A-Za-z0-9]+/arcgis/rest/services/[A-Za-z0-9_-]+/FeatureServer/[0-9]+$'
   or p_org_id !~ '^[A-Za-z0-9]{8,48}$'
   or length(p_org_title) not between 5 and 150
   or lower(p_org_title) not like '%' ||lower(split_part(root.jurisdiction_label,',',1))||'%'
   or not exists(select 1 from public.gis_verification_profiles
       where source_key=p_parent_source_key and profile_status='verified')
   or exists(select 1 from public.trusted_flock_gis_sources
       where source_key=p_source_key or gis_layer_url=p_gis_layer_url)
  then
   raise exception 'Original government endorsement and ArcGIS organization evidence not independently verified';
  end if;
  if jsonb_typeof(p_locations)<>'array'
     or jsonb_array_length(p_locations) not between 1 and 250 then
    raise exception 'Flock source inventory absent or truncated';
  end if;
  for loc in select value from jsonb_array_elements(p_locations) as value
  loop
    if jsonb_typeof(loc)<>'object'
       or jsonb_typeof(loc->'id')<>'number'
       or jsonb_typeof(loc->'lat')<>'number'
       or jsonb_typeof(loc->'lon')<>'number'
       or loc->>'id' !~ '^[0-9]{1,10}$'
    then raise exception 'Malformed independently endorsed camera point';end if;
    point_oid:=(loc->>'id')::integer;
    y:=(loc->>'lat')::double precision;
    x:=(loc->>'lon')::double precision;
    if point_oid<=0 or point_oid=any(ids)
       or y<parent.bounds_south or y>parent.bounds_north
       or x<parent.bounds_west or x>parent.bounds_east then
      raise exception 'Government-endorsed camera feature out of bounds or duplicate';
    end if;
    ids:=array_append(ids,point_oid);
    if exists(select 1 from public.flock_camera_locations c
      where c.verification_status='verified' and c.location_accuracy='exact'
        and abs(c.latitude-y)<0.00075
        and abs(c.longitude-x)<0.00075/greatest(cos(radians(y)),0.1)) then
      raise exception 'Potential duplicate already verified camera';
    end if;
    pts:=pts+1;
  end loop;
  insert into public.trusted_flock_gis_sources(
    source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
    expected_camera_type_field,expected_id_field,
    bounds_south,bounds_west,bounds_north,bounds_east,
    source_status,review_basis,reviewed_at
  ) values(
    p_source_key,p_gis_layer_url,p_disclosure_url,parent.jurisdiction_label,
    coalesce(p_vendor_field,'FlockLayer'),'OBJECTID',
    parent.bounds_south,parent.bounds_west,parent.bounds_north,parent.bounds_east,
    'verified',
    'Explicit original government Flock page directly links this exact ArcGIS feature layer, which has a corroborated agency-named ArcGIS organization and a bounded independently validated camera point inventory. Endorsed GIS, NOT government-owned hosting.',
    now()
  );
  insert into public.gis_verification_profiles(
    source_key,expected_layer_name,identity_mode,vendor_field,camera_id_field,
    service_evidence_mode,profile_status,review_basis
  ) values(
    p_source_key,p_layer_name,'official_flock_layer',p_vendor_field,p_camera_id_field,
    'listed_flock_layer','verified',
    'Original government-authenticated Flock page hyperlinks directly to this individually identifiable point layer; ArcGIS organization verified separately; exact feature identities and bounded nonduplicated geographic locations are rechecked.'
  );
  insert into public.official_external_flock_gis_authorities(
    source_key,parent_source_key,government_disclosure_url,gis_layer_url,
    original_page_sha256,original_layer_sha256,arcgis_org_id,arcgis_org_title,
    government_link_method
  ) values(
    p_source_key,p_parent_source_key,p_disclosure_url,p_gis_layer_url,
    p_page_sha256,p_layer_sha256,p_org_id,p_org_title,lead.discovery_method
  );
  return true;
end;
$external_register$;
