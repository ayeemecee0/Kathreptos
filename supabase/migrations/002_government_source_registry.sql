-- Private registry: discovered portals are not automatically trusted.
create table if not exists public.government_source_registry (
  id uuid primary key default gen_random_uuid(),
  source_url text not null unique check (source_url ~* '^https://'),
  host text not null,
  source_kind text not null check (source_kind in ('legistar','government_portal','procurement','transparency')),
  jurisdiction_label text,
  verification_status text not null default 'candidate'
    check (verification_status in ('candidate','verified','rejected')),
  evidence_url text,
  discovered_at timestamptz not null default now(),
  last_checked_at timestamptz,
  last_error text
);
create index if not exists government_source_registry_status_idx
  on public.government_source_registry(verification_status,source_kind);
alter table public.government_source_registry enable row level security;
revoke all on public.government_source_registry from anon, authenticated;
