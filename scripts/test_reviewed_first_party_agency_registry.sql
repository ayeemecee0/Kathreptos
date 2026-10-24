-- Disposable database regression. All synthetic records are rolled back,
-- no source trust or camera can be promoted in production by this file.
begin;
do $qa$
begin
 if has_table_privilege('anon','public.reviewed_first_party_gis_roots','SELECT')
  or has_table_privilege('authenticated','public.reviewed_first_party_gis_roots','SELECT')
  or has_table_privilege('service_role','public.reviewed_first_party_gis_roots','INSERT')
  or has_table_privilege('service_role','public.reviewed_first_party_gis_roots','UPDATE')
  or has_function_privilege('anon','public.register_reviewed_first_party_flock_source(text,text,text,text,text,text,jsonb)','EXECUTE')
  or has_function_privilege('authenticated','public.register_reviewed_first_party_flock_source(text,text,text,text,text,text,jsonb)','EXECUTE')
 then raise exception 'Independent agency review registry exposed to untrusted actors'; end if;
 if (select count(*) from public.reviewed_first_party_gis_roots where source_key='agency_alachua_fl' and review_status='verified')<>1 then
  raise exception 'Previously independently reviewed original agency source not migrated';
 end if;
end $qa$;
insert into public.reviewed_first_party_gis_roots
 (source_key,agency_page_url,agency_portal_url,gis_layer_url,jurisdiction_label,
 bounds_south,bounds_west,bounds_north,bounds_east,review_basis,reviewed_at,review_status)
values
 ('agency_ci_testtown_oh','https://gis.testtown.oh.gov/original',
 'https://maps.testtown.oh.gov/',
 'https://gis.testtown.oh.gov/server/rest/services/Police/Flock_Cameras/FeatureServer/0',
 'Testtown, OH',39.1,-83.1,39.5,-82.8,
 'DISPOSABLE CI synthetic agency source. This explicitly tests registry-driven original agency point confirmation, independently constrained geographies, original point source consistency, and lack of any ability for outside records or service role to invent public camera pins. This record has no production meaning.',
 now(),'verified');
insert into public.flock_gis_source_candidates(
  gis_layer_url,layer_name,geometry_type,object_id_field,
  layer_purpose,public_gov_context_url,trust_status)
values('https://gis.testtown.oh.gov/server/rest/services/Police/Flock_Cameras/FeatureServer/0',
'Flock Cameras','esriGeometryPoint','objectid',
'Disposable original-government city source regression with fictional points only, not production camera locations.',
'https://gis.testtown.oh.gov/original','unverified');
-- Unapproved/withdrawn/incorrect GIS source cannot self-authorize.
do $qa$
begin
 begin
   perform public.register_reviewed_first_party_flock_source(
    'agency_unreviewed_oh',repeat('a',64),repeat('b',64),'Flock Cameras',
    'objectid','arcgis_typed_objectid','[{"id":1,"lat":39.2,"lon":-83.0}]'::jsonb);
   raise exception 'Unreviewed agency camera source was approved';
 exception when raise_exception then
   if sqlerrm='Unreviewed agency camera source was approved' then raise;end if;
 end;
end $qa$;
do $qa$
declare ok boolean;
begin
 ok:=public.register_reviewed_first_party_flock_source(
   'agency_ci_testtown_oh',repeat('a',64),repeat('b',64),'Flock Cameras',
   'objectid','arcgis_typed_objectid',
   '[{"id":10,"lat":39.20,"lon":-83.0},{"id":11,"lat":39.25,"lon":-82.95}]'::jsonb);
 if ok is distinct from true then raise exception 'Generic reviewed source registration did not work';end if;
 if (select count(*) from public.first_party_agency_gis_receipts
    where source_key='agency_ci_testtown_oh' and original_camera_count=2)<>1 then
    raise exception 'Government original-source attestation not retained';end if;
 if (select count(*) from public.trusted_flock_gis_sources
    where source_key='agency_ci_testtown_oh' and source_status='verified')<>1 then
    raise exception 'Generic source not registered as owner-reviewed';end if;
 if (select count(*) from public.flock_camera_locations
    where source_url like '%testtown.oh.gov%')<>0 then
    raise exception 'Unpublished synthetic source was exposed as a camera';end if;
end $qa$;
-- Source registration must not approve additional fictional camera points
-- on a second invocation, and cannot supersede prior verified evidence.
do $qa$
begin
 begin
  perform public.register_reviewed_first_party_flock_source(
   'agency_ci_testtown_oh',repeat('a',64),repeat('b',64),'Flock Cameras',
   'objectid','arcgis_typed_objectid','[{"id":12,"lat":39.2,"lon":-83.0}]'::jsonb);
  raise exception 'Duplicate source authority reapproved';
 exception when raise_exception then
  if sqlerrm='Duplicate source authority reapproved' then raise;end if;
 end;
end $qa$;
rollback;
