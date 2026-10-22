-- 034 - independently verified municipal host inheritance for *additional* Flock layers.
-- Source approval is scoped to one exact camera layer. An ArcGIS search hit or
-- shared Esri-hosted map cannot approve itself. Both DB and live verifier block
-- candidate layers whose coordinates overlap existing verified camera points.
create table if not exists public.derived_government_camera_authorities (
  source_key text primary key references public.trusted_flock_gis_sources(source_key),
  parent_source_key text not null references public.trusted_flock_gis_sources(source_key),
  government_gis_url text not null,
  layer_sha256 text not null check(layer_sha256 ~ '^[a-f0-9]{64}$'),
  location_count integer not null check(location_count between 1 and 300),
  recorded_at timestamptz not null default now(),
  check(source_key<>parent_source_key)
);
alter table public.derived_government_camera_authorities enable row level security;
revoke all on public.derived_government_camera_authorities from public,anon,authenticated,service_role;
grant select on public.derived_government_camera_authorities to service_role;

create or replace function public.register_derived_government_flock_gis(
 p_parent_source_key text,p_source_key text,p_layer_url text,
 p_layer_name text,p_camera_id_field text,p_layer_sha256 text,
 p_locations jsonb
) returns boolean language plpgsql security definer set search_path=''
as $derived_register$
declare
  parent public.trusted_flock_gis_sources%rowtype;
  root public.gis_government_host_authorities%rowtype;
  candidate public.flock_gis_source_candidates%rowtype;
  loc jsonb;
  x double precision;
  y double precision;
  point_oid integer;
  pts int := 0;
  ids int[] := '{}'::int[];
  inferred_path text;
begin
  select * into parent from public.trusted_flock_gis_sources
   where source_key=p_parent_source_key and source_status='verified';
  select * into root from public.gis_government_host_authorities
   where authority_key=p_parent_source_key and verification_status='verified';
  select * into candidate from public.flock_gis_source_candidates
   where gis_layer_url=p_layer_url and trust_status='unverified';
  if parent.source_key is null or root.authority_key is null
   or candidate.gis_layer_url is null
   or p_source_key !~ '^gis_[a-z0-9_]{6,46}$'
   or p_source_key=p_parent_source_key
   or p_layer_sha256 !~ '^[a-f0-9]{64}$'
   or candidate.layer_name<>p_layer_name
   or candidate.geometry_type<>'esriGeometryPoint'
   or candidate.object_id_field<>'OBJECTID'
   or p_layer_name !~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$'
   or p_camera_id_field not in ('NAME','CameraID','ID','Camera_ID')
   or parent.gis_layer_url<>'https://' ||root.government_gis_host||root.allowed_layer_path
   or parent.jurisdiction_label<>root.jurisdiction_label
   or parent.government_evidence_url<>root.official_government_page
   or p_layer_url !~ '^https://[a-z0-9.-]+/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'
  then raise exception 'Derived GIS source not proven to be another independently identified government layer';end if;
  inferred_path:=substring(p_layer_url from length('https://' ||root.government_gis_host)+1);
  if p_layer_url<>'https://'||root.government_gis_host||inferred_path
     or inferred_path=root.allowed_layer_path
     or exists(select 1 from public.trusted_flock_gis_sources where gis_layer_url=p_layer_url)
     or not exists(select 1 from public.gis_verification_profiles
         where source_key=p_parent_source_key and profile_status='verified') then
    raise exception 'Not a distinct approved-host layer';
  end if;
  if jsonb_typeof(p_locations)<>'array'
     or jsonb_array_length(p_locations) not between 1 and 300 then
    raise exception 'Incomplete or oversized original GIS geometry inventory';
  end if;
  for loc in select value from jsonb_array_elements(p_locations) as value
  loop
    if jsonb_typeof(loc)<>'object'
       or jsonb_typeof(loc->'id')<>'number'
       or jsonb_typeof(loc->'lat')<>'number'
       or jsonb_typeof(loc->'lon')<>'number'
       or loc->>'id' !~ '^[0-9]{1,10}$'
    then raise exception 'Unverified government camera coordinates';end if;
    point_oid:=(loc->>'id')::integer;
    y:=(loc->>'lat')::double precision;
    x:=(loc->>'lon')::double precision;
    if point_oid<=0 or point_oid=any(ids)
       or y<parent.bounds_south or y>parent.bounds_north
       or x<parent.bounds_west or x>parent.bounds_east then
       raise exception 'Government GIS points duplicate IDs or lie outside approved jurisdiction';
    end if;
    ids:=array_append(ids,point_oid);
    -- Nearby records are held: the same municipal GIS pin may be exposed in
    -- multiple layers. Never inflate coverage from a duplicate source.
    if exists(
      select 1 from public.flock_camera_locations c
      where c.verification_status='verified' and c.location_accuracy='exact'
        and c.jurisdiction_label=parent.jurisdiction_label
        and abs(c.latitude-y)<0.00075 and
            abs(c.longitude-x)<(0.00075/cos(radians(y))::double precision)
    ) then
      raise exception 'Possible already published government camera: do not duplicate';
    end if;
    pts:=pts+1;
  end loop;
  insert into public.gis_government_host_authorities(
   authority_key,government_gis_host,official_government_page,
   jurisdiction_label,allowed_layer_path,expected_layer_name,
   bounds_south,bounds_west,bounds_north,bounds_east,
   verification_status,independently_reviewed_at,trust_explanation
  ) values(
   p_source_key,root.government_gis_host,root.official_government_page,
   root.jurisdiction_label,inferred_path,p_layer_name,
   root.bounds_south,root.bounds_west,root.bounds_north,root.bounds_east,
   'verified',now(),
   'Automated restricted inheritance from independently authenticated municipality GIS host; exact additional Flock Cameras point layer and bounded live inventory independently rechecked. Reject potential camera duplicates. No operational/read claim.'
  );
  insert into public.trusted_flock_gis_sources(
   source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
   expected_camera_type_field,expected_id_field,
   bounds_south,bounds_west,bounds_north,bounds_east,source_status,review_basis,reviewed_at
  ) values(
   p_source_key,p_layer_url,root.official_government_page,root.jurisdiction_label,
   'FlockLayer','OBJECTID',root.bounds_south,root.bounds_west,
   root.bounds_north,root.bounds_east,'verified',
   'Automatic qualified second camera layer on existing independently reviewed municipal GIS host. Source, schema, original camera identifiers, bounded georeferenced points, and duplicate exclusions checked.',now()
  );
  insert into public.gis_verification_profiles(
   source_key,expected_layer_name,identity_mode,vendor_field,camera_id_field,
   service_evidence_mode,profile_status,review_basis
  ) values(
   p_source_key,p_layer_name,'official_flock_layer',null,p_camera_id_field,
   'listed_flock_layer','verified',
   'Automatically inherited from existing government-owned GIS host, bound to exact additional verified Flock Cameras point layer, with original camera identifier and non-overlapping official coordinates.'
  );
  insert into public.derived_government_camera_authorities(
   source_key,parent_source_key,government_gis_url,layer_sha256,location_count
  ) values(p_source_key,p_parent_source_key,p_layer_url,p_layer_sha256,pts);
  return true;
end;
$derived_register$;

revoke all on function public.register_derived_government_flock_gis(text,text,text,text,text,text,jsonb)
 from public,anon,authenticated,service_role;
grant execute on function public.register_derived_government_flock_gis(text,text,text,text,text,text,jsonb)
 to service_role;

create or replace function public.revoke_derived_when_parent_camera_gis_revoked()
returns trigger language plpgsql security definer set search_path=''
as $revoke_descendants$
begin
 if old.source_status='verified' and new.source_status<>'verified' then
   update public.gis_government_host_authorities a
      set verification_status='revoked'
     from public.derived_government_camera_authorities d
     where d.parent_source_key=old.source_key
       and d.source_key=a.authority_key and a.verification_status='verified';
 end if;
 return new;
end;
$revoke_descendants$;
revoke all on function public.revoke_derived_when_parent_camera_gis_revoked()
 from public,anon,authenticated,service_role;
drop trigger if exists revoke_derived_when_parent_camera_gis_revoked
 on public.trusted_flock_gis_sources;
create trigger revoke_derived_when_parent_camera_gis_revoked
after update of source_status on public.trusted_flock_gis_sources
for each row execute function public.revoke_derived_when_parent_camera_gis_revoked();
