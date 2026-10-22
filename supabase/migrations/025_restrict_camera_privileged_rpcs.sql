-- Security remediation: several privileged functions received direct anon/
-- authenticated EXECUTE grants from project default privileges despite an
-- earlier REVOKE FROM PUBLIC. Restrict them explicitly by role.
-- Public read-only predicates used by camera RLS intentionally remain callable.

revoke all on function public.promote_owner_bound_gis_source(text,text,text)
  from public,anon,authenticated;
grant execute on function public.promote_owner_bound_gis_source(text,text,text)
  to service_role;

do $hardening$
declare item record;
begin
  for item in
    select p.oid::regprocedure as signature
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
     where n.nspname='public' and p.prosecdef
       and p.prorettype='pg_catalog.trigger'::regtype
  loop
    execute format('revoke execute on function %s from public,anon,authenticated',
      item.signature);
  end loop;
end;
$hardening$;

-- Guard against accidentally regranting this sensitive promotion function
-- during future migrations.
comment on function public.promote_owner_bound_gis_source(text,text,text)
is 'Service-role-only, narrow owner-root camera GIS promotion. Never grant EXECUTE to anon or authenticated; hash params alone do not attest a live source.';
