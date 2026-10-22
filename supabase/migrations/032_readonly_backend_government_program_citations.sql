-- Backend government-source verification needs read-only access to citations.
-- Public evidence remains RLS-filtered; no backend insert/update/delete grant.
grant select on public.flock_documented_programs to service_role;
revoke insert,update,delete,truncate on public.flock_documented_programs from service_role;
