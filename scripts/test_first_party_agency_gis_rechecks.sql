-- CI-only original publisher freshness checks; fully synthetic and rollback-only.
begin;
do $qa$
begin
 if has_table_privilege('anon','public.first_party_agency_gis_recheck_history','SELECT')
    or has_table_privilege('authenticated','public.first_party_agency_gis_recheck_history','SELECT')
    or has_table_privilege('service_role','public.first_party_agency_gis_recheck_history','INSERT')
    or has_function_privilege('anon',
        'public.refresh_reviewed_first_party_gis_receipt(text,text,text,integer,text)','EXECUTE')
    or has_function_privilege('authenticated',
        'public.refresh_reviewed_first_party_gis_receipt(text,text,text,integer,text)','EXECUTE')
 then raise exception 'Untrusted role can manipulate original government publisher audit receipts'; end if;
end $qa$;
insert into public.reviewed_first_party_gis_roots
 (source_key,agency_page_url,agency_portal_url,gis_layer_url,jurisdiction_label,
 bounds_south,bounds_west,bounds_north,bounds_east,review_basis,reviewed_at,review_status)
values
 ('agency_ci_recheck_oh','https://gis.testtown.oh.gov/original',
 'https://maps.testtown.oh.gov/',
 'https://gis.testtown.oh.gov/server/rest/services/Police/Flock_Cameras/FeatureServer/0',
 'Testtown, OH',39.1,-83.1,39.5,-82.8,
 'DISPOSABLE CI source used solely to exercise time-separated original-agency publisher evidence rechecks with a vetted private trust root and canonical camera identity. No real installed camera or operational law-enforcement claim is ever made by this synthetic fixture.',
 now(),'verified');
insert into public.flock_gis_source_candidates(
 gis_layer_url,layer_name,geometry_type,object_id_field,
 layer_purpose,public_gov_context_url,trust_status)
values('https://gis.testtown.oh.gov/server/rest/services/Police/Flock_Cameras/FeatureServer/0',
 'Flock Cameras','esriGeometryPoint','objectid',
 'Synthetic original-government fixture only; not real installations.',
 'https://gis.testtown.oh.gov/original','unverified');
do $qa$
begin
 if public.register_reviewed_first_party_flock_source(
  'agency_ci_recheck_oh',repeat('a',64),repeat('b',64),
  'Flock Cameras','objectid','arcgis_typed_objectid',
  '[{"id":5,"lat":39.2,"lon":-83.0}]'::jsonb) is distinct from true
 then raise exception 'Synthetic reviewed source registration failed'; end if;
 if public.refresh_reviewed_first_party_gis_receipt(
  'agency_ci_recheck_oh',repeat('c',64),repeat('d',64),2,
  'arcgis_typed_objectid') is distinct from true
 then raise exception 'Independent government GIS provenance recheck refused';end if;
 if (select count(*) from public.first_party_agency_gis_recheck_history
      where source_key='agency_ci_recheck_oh')<>1
 then raise exception 'Original agency provenance audit history not append-only';end if;
 if not exists(select 1 from public.first_party_agency_gis_receipts
      where source_key='agency_ci_recheck_oh'
        and original_page_sha256=repeat('c',64)
        and full_layer_points_sha256=repeat('d',64)
        and original_camera_count=2)
 then raise exception 'Fresh original publisher evidence receipt not updated';end if;
end $qa$;
do $qa$
begin
 begin
  perform public.refresh_reviewed_first_party_gis_receipt(
   'agency_ci_recheck_oh',repeat('e',64),repeat('f',64),2,
   'named_camera_id');
  raise exception 'Changed original typed ObjectID identity improperly accepted';
 exception when raise_exception then
  if sqlerrm='Changed original typed ObjectID identity improperly accepted' then raise;end if;
 end;
end $qa$;
update public.reviewed_first_party_gis_roots
 set review_status='revoked' where source_key='agency_ci_recheck_oh';
do $qa$
begin
 begin
  perform public.refresh_reviewed_first_party_gis_receipt(
   'agency_ci_recheck_oh',repeat('e',64),repeat('f',64),2,
   'arcgis_typed_objectid');
  raise exception 'Revoked original agency evidence improperly refreshed';
 exception when raise_exception then
  if sqlerrm='Revoked original agency evidence improperly refreshed' then raise;end if;
 end;
 if exists(select 1 from public.first_party_agency_gis_receipts
    where source_key='agency_ci_recheck_oh'
     and original_page_sha256=repeat('e',64))
 then raise exception 'Failed original government page recheck changed trusted receipt';end if;
end $qa$;
rollback;
