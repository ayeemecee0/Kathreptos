-- Nationwide candidate discovery, never an authority or camera registry.
-- Private search leads can originate from unknown government jurisdictions;
-- do not assign a municipality from a search query or DNS hostname.
create table if not exists public.government_gis_search_queue (
  page_url text primary key check(
    length(page_url) between 20 and 1500 and
    page_url ~ '^https://([a-zA-Z0-9-]+\.)+gov(/|$)'),
  state_search_hint text not null check(length(state_search_hint) between 2 and 90),
  discovery_query text not null check(length(discovery_query) between 8 and 220),
  page_sha256 text not null check(page_sha256 ~ '^[a-f0-9]{64}$'),
  gis_links jsonb not null default '[]'::jsonb
    check (jsonb_typeof(gis_links)='array' and jsonb_array_length(gis_links)<=25),
  evidence_excerpt text not null check(length(evidence_excerpt) between 12 and 600),
  candidate_status text not null default 'unverified'
    check(candidate_status in ('unverified','discarded')),
  first_discovered_at timestamptz not null default now(),
  last_observed_at timestamptz not null default now(),
  check (last_observed_at>=first_discovered_at)
);
alter table public.government_gis_search_queue enable row level security;
revoke all on public.government_gis_search_queue from public,anon,authenticated,service_role;
grant select,insert on public.government_gis_search_queue to service_role;
grant update(last_observed_at) on public.government_gis_search_queue to service_role;
create index if not exists government_gis_search_queue_recent_idx
 on public.government_gis_search_queue(last_observed_at desc);
comment on table public.government_gis_search_queue is
'Unverified nationwide Flock/GIS disclosure pages found through search. A search hit, a .gov domain, or an ArcGIS layer title does not authorize public camera publication.';
