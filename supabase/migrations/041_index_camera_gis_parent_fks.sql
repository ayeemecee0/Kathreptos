-- 041: Speed parent-source revocation and endorsement lookups.
create index if not exists derived_gov_camera_authorities_parent_fk_idx
 on public.derived_government_camera_authorities(parent_source_key);
create index if not exists external_flock_gis_parent_fk_idx
 on public.official_external_flock_gis_authorities(parent_source_key);
