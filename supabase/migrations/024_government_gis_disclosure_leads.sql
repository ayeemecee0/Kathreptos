-- Private audit trail of independently fetched municipal pages that link
-- to camera GIS layers. Discovery ≠ authority ≠ a verified camera placement.
create table if not exists public.government_gis_disclosure_leads (
  disclosure_url text not null check (disclosure_url ~ '^https://[A-Za-z0-9.-]+/[^[:space:]]*$'),
  gis_layer_url text not null check (
    gis_layer_url ~ '^https://[A-Za-z0-9.-]+/.+/(?:FeatureServer|MapServer)/[0-9]+$'),
  jurisdiction_label text not null check(length(btrim(jurisdiction_label)) between 5 and 150),
  discovery_method text not null check
    (discovery_method in ('government_page_direct_anchor_v1','government_page_same_host_depth1_v1')),
  link_label text not null check(length(btrim(link_label)) between 3 and 220),
  government_page_sha256 text not null check(government_page_sha256 ~ '^[0-9a-f]{64}$'),
  source_host_scope text not null check(length(source_host_scope) between 4 and 150),
  layer_host text not null check(length(layer_host) between 4 and 150),
  layer_metadata_status text not null default 'unverified'
    check(layer_metadata_status in ('unverified','point_layer_verified','rejected')),
  first_discovered_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  primary key(disclosure_url,gis_layer_url),
  check (length(disclosure_url)<=1500 and length(gis_layer_url)<=2048),
  check (last_seen_at>=first_discovered_at)
);
create index if not exists government_gis_disclosure_recent_idx
 on public.government_gis_disclosure_leads(last_seen_at desc);
alter table public.government_gis_disclosure_leads enable row level security;
revoke all on public.government_gis_disclosure_leads from anon,authenticated,service_role;
grant select,insert on public.government_gis_disclosure_leads to service_role;
grant update(last_seen_at) on public.government_gis_disclosure_leads to service_role;
comment on table public.government_gis_disclosure_leads is
'Private direct government-page -> GIS-link evidence, nonauthoritative until independent official layer provenance and manufacturer-specific coordinates verified. Never exposed to anonymous users.';
