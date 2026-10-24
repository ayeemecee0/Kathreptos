-- CI-only source-scope regression. No synthetic camera can reach live map.
begin;
do $qa$
begin
 if has_function_privilege('anon',
   'public.register_first_party_agency_flock_source(text,text,text,text,text,text,jsonb)'::regprocedure,
   'EXECUTE')
   or has_function_privilege('authenticated',
   'public.register_first_party_agency_flock_source(text,text,text,text,text,text,jsonb)'::regprocedure,
   'EXECUTE')
 then raise exception 'Untrusted role can approve agency GIS source'; end if;
end $qa$;
insert into public.flock_gis_source_candidates(
  gis_layer_url,layer_name,geometry_type,object_id_field,
  layer_purpose,public_gov_context_url,trust_status)
values(
 'https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0',
 'Flock Cameras','esriGeometryPoint','objectid',
 'CI-only agency GIS profile; no actual cameras or original-government receipt are claimed.',
 'https://growth-management.alachuacounty.us/GIS','unverified')
on conflict(gis_layer_url) do nothing;
do $qa$
declare success boolean;
begin
 -- Caller is the disposable CI DB owner; the function itself runs with the
 -- same definer privileges as in live production.
 success:=public.register_first_party_agency_flock_source(
  'agency_alachua_fl', repeat('a',64),repeat('b',64),
  'Flock Cameras','objectid','arcgis_typed_objectid',
  '[{"id":1,"lat":29.6,"lon":-82.3},{"id":2,"lat":29.61,"lon":-82.32}]'::jsonb);
 if not success then raise exception 'Pinned agency source registration failed';end if;
 if (select count(*) from public.first_party_agency_gis_receipts
     where source_key='agency_alachua_fl' and original_camera_count=2)<>1
 then raise exception 'No private original government source evidence receipt';end if;
 if not exists(select 1 from public.gis_verification_profiles
    where source_key='agency_alachua_fl' and profile_status='verified'
      and camera_id_field='objectid')
 then raise exception 'Original typed ObjectID profile missing';end if;
 if exists(select 1 from public.flock_camera_locations
    where source_url like '%alachuacounty.us%')
 then raise exception 'Source registration alone published synthetic locations';end if;
end $qa$;
-- An unrelated government domain, other camera layer or outside-county pin
-- cannot inherit the pinned county agency authority.
do $qa$
begin
 begin
 perform public.register_first_party_agency_flock_source(
  'agency_alachua_bad',repeat('a',64),repeat('b',64),
  'Flock Cameras','OBJECTID','arcgis_typed_objectid',
  '[{"id":3,"lat":29.6,"lon":-82.3}]'::jsonb);
 raise exception 'Unapproved GIS publisher identity accepted';
 exception when raise_exception then
  if sqlerrm='Unapproved GIS publisher identity accepted' then raise;end if;
 end;
end $qa$;
rollback;
