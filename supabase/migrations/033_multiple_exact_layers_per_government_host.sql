-- An approved municipal GIS host can publish more than one independent
-- camera service. Trust must remain scoped to one exact host + layer path;
-- a host approval is NEVER a wildcard authority for its other services.
alter table public.gis_government_host_authorities
  drop constraint if exists gis_government_host_authorities_government_gis_host_key;
alter table public.gis_government_host_authorities
  add constraint gis_government_host_authorities_host_layer_key
    unique (government_gis_host, allowed_layer_path);

comment on table public.gis_government_host_authorities is
'Owner-reviewed exact original-government host-and-layer bindings. Several independently reviewed camera layers may share a municipal host, but authorization and revocation remain source_key-scoped. Discovery does not approve new layers.';
