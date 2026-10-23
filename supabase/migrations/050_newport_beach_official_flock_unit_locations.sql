-- 050: Original City of Newport Beach publicly listed Flock GIS units.
-- Sources independently cross-checked:
-- 1. City GIS public catalog (guest-visible NewportGIS) lists Flock Unit
--    Locations #299 and links EmployeeMasterMap/MapServer on nbgis host.
-- 2. City's own Newport Beach Police/Legistar Flock ALPR documents establish
--    that the City uses Flock technology, independently of GIS layer title.
-- 3. Read-only live City-host GIS probe found 69 georeferenced in-area
--    point features with 69 nonempty unique FlockUnitNo identifiers and
--    typed ArcGIS OBJECTID_12 object identities; returnIdsOnly verified.
--    Staff/notes/address attributes are NOT copied into the public database.
-- A publicly listed Flock unit position is NOT proof of a working ALPR.

alter table public.gis_government_host_authorities
  drop constraint if exists gis_government_host_authorities_expected_layer_name_check;
alter table public.gis_government_host_authorities
  add constraint gis_government_host_authorities_expected_layer_name_check
  check(expected_layer_name ~* '^(flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?|flock unit locations)$');

alter table public.gis_verification_profiles
  drop constraint if exists gis_verification_profiles_check;
alter table public.gis_verification_profiles
  add constraint gis_verification_profiles_check
  check(
   (identity_mode='per_feature_vendor' and
    vendor_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$')
   or (identity_mode='official_flock_layer'
     and expected_layer_name ~* '^(flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?|flock unit locations)$'
     and camera_id_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$'
     and (vendor_field is null or vendor_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$'))
  );

insert into public.gis_government_host_authorities(
 authority_key,government_gis_host,official_government_page,
 jurisdiction_label,allowed_layer_path,expected_layer_name,
 bounds_south,bounds_west,bounds_north,bounds_east,
 verification_status,independently_reviewed_at,trust_explanation
) values(
 'newport_beach_ca','nbgis.newportbeachca.gov',
 'https://nbgis.newportbeachca.gov/Geocortex/Essentials/REST/sites/NewportGIS/map/mapservices/7',
 'Newport Beach, CA',
 '/arcgis/rest/services/EmployeeMasterMap/MapServer/299',
 'Flock Unit Locations',
 33.52,-117.98,33.77,-117.69,'verified',now(),
 'City of Newport Beach GIS Division public NewportGIS Geocortex map catalog, accessed without authentication, explicitly lists Flock Unit Locations layer 299 and original city-operated nbgis.newportbeachca.gov ArcGIS EmployeeMasterMap service. The independent official City Council Flock ALPR contract agenda corroborates vendor/program identity. Read-only live GIS probe found 69 georeferenced point features within Newport Beach area with nonempty unique FlockUnitNo identifiers and original typed OBJECTID_12 values. Public republication includes only source-backed coordinates/IDs and minimal evidence; not any police notes, staff records, private vehicle details or real-time reader status.'
) on conflict(authority_key) do nothing;

insert into public.trusted_flock_gis_sources(
 source_key,gis_layer_url,government_evidence_url,jurisdiction_label,
 expected_camera_type_field,expected_id_field,
 bounds_south,bounds_west,bounds_north,bounds_east,
 source_status,review_basis,reviewed_at
) values(
 'newport_beach_ca',
 'https://nbgis.newportbeachca.gov/arcgis/rest/services/EmployeeMasterMap/MapServer/299',
 'https://nbgis.newportbeachca.gov/Geocortex/Essentials/REST/sites/NewportGIS/map/mapservices/7',
 'Newport Beach, CA','FlockUnitNo','OBJECTID_12',
 33.52,-117.98,33.77,-117.69,'verified',
 'City GIS public layer Flock Unit Locations directly lists original-government ArcGIS MapServer #299, with 69 bounded, individually identified Flock-unit points. No sensitive auxiliary GIS attributes, operational inferences or license plate read details may be published.',now()
) on conflict(source_key) do nothing;

insert into public.gis_verification_profiles(
 source_key,expected_layer_name,identity_mode,vendor_field,camera_id_field,
 service_evidence_mode,profile_status,review_basis
) values(
 'newport_beach_ca','Flock Unit Locations',
 'official_flock_layer',null,'FlockUnitNo',
 'listed_flock_layer','verified',
 'Original publicly indexed municipal Police GIS Flock Unit Locations point layer #299, authenticated to the City-hosted nbgis.newportbeachca.gov source and government metadata, with typed OBJECTID_12 IDs and a separate nonempty FlockUnitNo for each individual feature. No private auxiliary fields or operational status implied.'
) on conflict(source_key) do nothing;
