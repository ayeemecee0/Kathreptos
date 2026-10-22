-- 037: Allow only a tightly scoped backend RPC to mark an EXACT government
-- hyperlink receipt as having independently examined point-layer metadata.
-- An ArcGIS catalog title, another government's page, or a hash mismatch
-- cannot convert a private discovery lead to an endorsed source.
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
   or lead.discovery_method<>'government_page_direct_anchor_v1'
   or lead.layer_metadata_status not in ('unverified','point_layer_verified')
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
revoke all on function public.confirm_original_government_linked_point_layer(text,text,text,text)
 from public,anon,authenticated,service_role;
grant execute on function public.confirm_original_government_linked_point_layer(text,text,text,text)
 to service_role;
