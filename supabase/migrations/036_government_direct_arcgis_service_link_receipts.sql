-- Preserve distinct provenance when a government document hyperlinks to an
-- ArcGIS service root rather than a numbered feature layer. This is research
-- evidence only; not a source or camera approval.
alter table public.government_gis_disclosure_leads
  drop constraint if exists government_gis_disclosure_leads_discovery_method_check;
alter table public.government_gis_disclosure_leads
  add constraint government_gis_disclosure_leads_discovery_method_check
  check(discovery_method in (
    'government_page_direct_anchor_v1',
    'government_page_same_host_depth1_v1',
    'government_page_direct_service_v1'
  ));
