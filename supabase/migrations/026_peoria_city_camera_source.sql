-- Peoria, Arizona: independently reviewed city-operated Flock GIS source.
-- Confirmation: peoriaaz.gov city services link to gis.peoriaaz.gov, the
-- municipal PM/pmPublicWorks MapServer publishes an esriGeometryPoint layer
-- named 'Flock Cameras' (#286), with 74 nonempty CameraID entries and WGS84
-- coordinates within the Peoria vicinity in the first successful live probe.
-- This documents municipality GIS locations, NOT current camera operation.
insert into public.gis_government_host_authorities(
  authority_key,government_gis_host,official_government_page,
  jurisdiction_label,allowed_layer_path,expected_layer_name,
  bounds_south,bounds_west,bounds_north,bounds_east,
  verification_status,independently_reviewed_at,trust_explanation
) values (
  'peoria_az','gis.peoriaaz.gov',
  'https://devservices.peoriaaz.gov/devservices/Cap/CapHome.aspx?TabName=HOME&module=Planning',
  'Peoria, AZ','/arcgis/rest/services/PM/pmPublicWorks/MapServer/286','Flock Cameras',
  33.2,-113,34.5,-111.4,'verified',now(),
  'City of Peoria official development-services peoriaaz.gov page directly links to municipal gis.peoriaaz.gov GIS. Its Public Works MapServer explicitly advertises point layer Flock Cameras (#286), CameraID and Location fields. The independently executed bounded live source probe on 2026-10-22 found 74 valid GIS points, with no missing IDs or out-of-area geometry. GIS points are not attestation that devices are currently online.'
) on conflict(authority_key) do nothing;

insert into public.trusted_flock_gis_sources(
  source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
  expected_camera_type_field,expected_id_field,
  bounds_south,bounds_west,bounds_north,bounds_east,
  source_status,review_basis,reviewed_at
) values (
  'peoria_az',
  'https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer/286',
  'https://devservices.peoriaaz.gov/devservices/Cap/CapHome.aspx?TabName=HOME&module=Planning',
  'Peoria, AZ','FlockLayer','OBJECTID',
  33.2,-113,34.5,-111.4,'verified',
  'Original government GIS authority reviewed after fresh official Peoria development-services to GIS link, government service Flock Cameras point layer, and 74 individually labeled CameraID-bearing in-area features. Source records remain subject to daily revalidation and withdrawal.',now()
) on conflict(source_key) do nothing;
