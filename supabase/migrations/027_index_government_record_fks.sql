-- Non-destructive index repair from Supabase FK performance advisor.
-- Independently checked pg_constraint and existing indexes October 22, 2026.
create index if not exists actions_jurisdiction_fk_idx
  on public.actions(jurisdiction_id);
create index if not exists actions_source_fk_idx
  on public.actions(source_id);
create index if not exists contracts_source_fk_idx
  on public.contracts(source_id);
create index if not exists deployments_agency_fk_idx
  on public.deployments(agency_id);
create index if not exists deployments_source_fk_idx
  on public.deployments(source_id);
create index if not exists editorial_general_events_actor_fk_idx
  on public.editorial_general_events(actor_id);
create index if not exists editorial_general_reviews_reviewer_fk_idx
  on public.editorial_general_reviews(reviewed_by);
create index if not exists editorial_review_events_actor_fk_idx
  on public.editorial_review_events(actor_id);
