-- Defense in depth: a GitHub Actions service-role credential may discover and
-- queue leads but may not verify PUBLIC sources or publish/edit PUBLIC facts.
-- The database owner must deliberately review and publish editorial facts.
--
-- Existing reviewed/published records remain unchanged. This guard has no
-- effect on private government_source_registry verification or queue writes.

create or replace function public.guard_publication_from_workflow_service_role()
returns trigger
language plpgsql
set search_path = pg_catalog
as $editorial_guard$
begin
  if current_user = 'service_role' then
    if tg_table_name = 'sources' then
      if new.status = 'verified'
         or (tg_op = 'UPDATE' and old.status = 'verified') then
        raise exception 'Public source verification requires database-owner editorial review';
      end if;
    else
      if new.review_status = 'published'
         or (tg_op = 'UPDATE' and old.review_status = 'published') then
        raise exception 'Public fact publication requires database-owner editorial review';
      end if;
    end if;
  end if;
  return new;
end;
$editorial_guard$;

drop trigger if exists guard_workflow_sources_publication on public.sources;
create trigger guard_workflow_sources_publication
before insert or update on public.sources
for each row execute function public.guard_publication_from_workflow_service_role();

drop trigger if exists guard_workflow_actions_publication on public.actions;
create trigger guard_workflow_actions_publication
before insert or update on public.actions
for each row execute function public.guard_publication_from_workflow_service_role();

drop trigger if exists guard_workflow_contracts_publication on public.contracts;
create trigger guard_workflow_contracts_publication
before insert or update on public.contracts
for each row execute function public.guard_publication_from_workflow_service_role();

drop trigger if exists guard_workflow_deployments_publication on public.deployments;
create trigger guard_workflow_deployments_publication
before insert or update on public.deployments
for each row execute function public.guard_publication_from_workflow_service_role();
