-- Camera source freshness is operational metadata, distinct from immutable
-- evidence. Renew it only after a successful current official GIS recheck.
alter table public.flock_camera_locations
  add column if not exists last_source_recheck_at timestamptz not null default now();

revoke update(last_source_recheck_at) on public.flock_camera_locations from service_role;
grant update(last_source_recheck_at) on public.flock_camera_locations to service_role;

create or replace function public.guard_camera_source_recheck()
returns trigger language plpgsql set search_path=''
as $camera_recheck_guard$
begin
 if new.last_source_recheck_at < old.last_source_recheck_at
    or new.last_source_recheck_at > now()+interval '10 minutes' then
   raise exception 'Camera source recheck timestamp cannot be rolled back or future-dated';
 end if;
 return new;
end;
$camera_recheck_guard$;

drop trigger if exists guard_camera_source_recheck
 on public.flock_camera_locations;
create trigger guard_camera_source_recheck
before update on public.flock_camera_locations
for each row execute function public.guard_camera_source_recheck();

comment on column public.flock_camera_locations.last_source_recheck_at is
'Last source revalidation time (operational, not evidence). Original camera record facts and published_at remain immutable.';
