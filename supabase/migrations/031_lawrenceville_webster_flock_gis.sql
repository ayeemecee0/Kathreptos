-- Two additional owner-reviewed official municipal GIS sources, 2026-10-22.
-- Lawrenceville GA official GIS/Maps page links the city's own gisinfo
-- host AND publishes a separate original FLOCK Camera Map PDF.
-- The live government layer contains 55 point features, but CameraType
-- identifies only 45 as "PD Flock Camera"; ten "PD School Camera"
-- records MUST NOT be published as Flock cameras.
-- Webster TX official city website links www1.cityofwebster.com GIS;
-- the city-hosted service describes PD Flock plate-reader cameras
-- and has 53 in-city uniquely identified point features.
-- No source proves that a device is operational or reading any plate.

alter table public.gis_government_host_authorities
 drop constraint if exists gis_government_host_authorities_expected_layer_name_check;
alter table public.gis_government_host_authorities
 add constraint gis_government_host_authorities_expected_layer_name_check
 check(expected_layer_name ~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$');

alter table public.gis_verification_profiles
 drop constraint if exists gis_verification_profiles_check;
alter table public.gis_verification_profiles
 add constraint gis_verification_profiles_check
 check(
   (identity_mode='per_feature_vendor'
     and vendor_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$')
   or (identity_mode='official_flock_layer'
     and expected_layer_name ~* '^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$'
     and camera_id_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$'
     and (vendor_field is null or vendor_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$'))
 );

insert into public.gis_government_host_authorities(
 authority_key,government_gis_host,official_government_page,jurisdiction_label,
 allowed_layer_path,expected_layer_name,
 bounds_south,bounds_west,bounds_north,bounds_east,
 verification_status,independently_reviewed_at,trust_explanation
) values
('lawrenceville_ga','gisinfo.lawrencevillega.org',
 'https://www.lawrencevillega.org/592/GISMaps',
 'Lawrenceville, GA',
 '/server/rest/services/MyCityServices/MyCityServices/MapServer/29','Flock Cameras',
 33.75,-84.15,34.1,-83.85,'verified',now(),
 'City of Lawrenceville official GIS/Maps page links its own GIS portal at gisinfo.lawrencevillega.org and a FLOCK Camera Map document. Original MyCityServices MapServer point layer 29 is named Flock Cameras with CameraID and CameraType fields. Independently checked 55 point features; only 45 have CameraType PD Flock Camera, while ten PD School Camera records are excluded from publication.'),
('webster_tx','www1.cityofwebster.com',
 'https://www.webstertx.gov/868/Maps',
 'Webster, TX',
 '/arcgis/rest/services/Landbase/Cameras_Licence_Plates1/MapServer/0',
 'FLOCK Cameras - Webster PD',
 29.47,-95.20,29.61,-95.05,'verified',now(),
 'City of Webster official Maps page on webstertx.gov links to its municipal GIS web server www1.cityofwebster.com. The original Landbase/Cameras_Licence_Plates1 service explicitly says Webster PD FLOCK cameras for reading license plates; its exact point layer is FLOCK Cameras - Webster PD. Independently checked 53 unique in-city points, each carrying an individual ID; locations may change.')
on conflict(authority_key) do nothing;

insert into public.trusted_flock_gis_sources(
 source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
 expected_camera_type_field,expected_id_field,
 bounds_south,bounds_west,bounds_north,bounds_east,
 source_status,review_basis,reviewed_at
) values
('lawrenceville_ga',
 'https://gisinfo.lawrencevillega.org/server/rest/services/MyCityServices/MyCityServices/MapServer/29',
 'https://www.lawrencevillega.org/592/GISMaps','Lawrenceville, GA',
 'CameraType','OBJECTID',33.75,-84.15,34.1,-83.85,'verified',
 'City-owned public GIS service and a separate official Flock Camera Map are linked on the city GIS page. Current layer has 45 Flock-labeled points and ten excluded school cameras; manufacturer type must be checked on every future import.',now()),
('webster_tx',
 'https://www1.cityofwebster.com/arcgis/rest/services/Landbase/Cameras_Licence_Plates1/MapServer/0',
 'https://www.webstertx.gov/868/Maps','Webster, TX',
 'FlockLayer','OBJECTID',29.47,-95.20,29.61,-95.05,'verified',
 'Official city maps link municipal host; original Webster PD camera license-plate service and exact Flock PD layer independently verified with 53 identified points. Operational status and actual camera reads unknown.',now())
on conflict(source_key) do nothing;

insert into public.gis_verification_profiles(
 source_key,expected_layer_name,identity_mode,vendor_field,camera_id_field,
 service_evidence_mode,profile_status,review_basis
) values
('lawrenceville_ga','Flock Cameras','official_flock_layer','CameraType','CameraID',
 'listed_flock_layer','verified',
 'Official Lawrenceville GIS source includes ten PD School Camera point features that are NOT Flock ALPR cameras. Require per-feature CameraType explicitly saying Flock, in addition to the exact original municipal layer and CameraID.'),
('webster_tx','FLOCK Cameras - Webster PD','official_flock_layer',null,'ID',
 'explicit_flock_service_text','verified',
 'Exact Webster municipal original GIS service explicitly identifies Flock PD license-plate cameras in serviceDescription and point layer metadata. Every published point must include a valid original ID.')
on conflict(source_key) do nothing;
