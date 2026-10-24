-- 053: A single apparently complete government GIS snapshot may briefly omit a
-- camera. Require a second, time-separated complete inventory before
-- withdrawing an individual camera coordinate. Changes to entire source
-- authority remain subject to the existing immediate source-revocation path.

create table if not exists public.pending_gis_camera_withdrawals (
  source_key text not null references public.trusted_flock_gis_sources(source_key),
  record_key text not null references public.flock_camera_locations(record_key),
  first_missing_at timestamptz not null default now(),
  last_missing_at timestamptz not null default now(),
  complete_inventory_observations smallint not null default 1
    check (complete_inventory_observations between 1 and 2),
  primary key (source_key,record_key),
  check(last_missing_at>=first_missing_at)
);
create index if not exists pending_gis_camera_withdrawals_record_idx
  on public.pending_gis_camera_withdrawals(record_key);
alter table public.pending_gis_camera_withdrawals enable row level security;
revoke all on public.pending_gis_camera_withdrawals
  from public,anon,authenticated,service_role;

create or replace function public.confirm_gis_camera_withdrawals(
  p_source_key text, p_missing_keys text[]
) returns jsonb language plpgsql security definer set search_path=''
as $confirm_gis_withdrawals$
declare
  v_record text;
  v_prefix text := 'gis-' || p_source_key || '-';
  v_pending public.pending_gis_camera_withdrawals%rowtype;
  v_confirmed text[] := '{}'::text[];
  v_pending_count integer := 0;
  v_source_status text;
begin
  if p_source_key is null or p_source_key !~ '^[a-z0-9_]{2,90}$'
    or p_missing_keys is null or
       coalesce(array_length(p_missing_keys,1),0)>3000 then
    raise exception 'Invalid GIS source withdrawal evidence';
  end if;

  select source_status into v_source_status
    from public.trusted_flock_gis_sources where source_key=p_source_key;
  if v_source_status is distinct from 'verified' then
    raise exception 'Unverified government GIS source cannot reconcile withdrawal';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('katoptron:gis-withdrawals:' || p_source_key,0));

  if exists(select 1 from unnest(p_missing_keys) k
      where k is null or left(k,length(v_prefix))<>v_prefix) or
     coalesce(array_length(p_missing_keys,1),0) <>
       (select count(distinct k) from unnest(p_missing_keys) k) then
    raise exception 'Missing camera IDs cross source boundaries or duplicate';
  end if;

  -- Check that each alleged disappearance was previously a genuinely
  -- published exact camera on this same approved source.
  if exists (
    select 1 from unnest(p_missing_keys) k
    where not exists (
      select 1 from public.flock_camera_locations c
      where c.record_key=k and c.verification_status='verified'
      and c.location_accuracy='exact'
      and left(c.record_key,length(v_prefix))=v_prefix)
  ) then
    raise exception 'Missing-camera evidence references an unverified or foreign record';
  end if;

  -- If a camera reappears in a complete source inventory, discard its
  -- withdrawal suspicion. This must run even when p_missing_keys is empty.
  delete from public.pending_gis_camera_withdrawals
    where source_key=p_source_key
      and not (record_key=any(p_missing_keys));

  foreach v_record in array p_missing_keys loop
    select * into v_pending
      from public.pending_gis_camera_withdrawals
      where source_key=p_source_key and record_key=v_record for update;

    if v_pending.record_key is null then
      insert into public.pending_gis_camera_withdrawals(
        source_key,record_key,first_missing_at,last_missing_at,
        complete_inventory_observations
      ) values(p_source_key,v_record,now(),now(),1);
      v_pending_count:=v_pending_count+1;
    elsif v_pending.complete_inventory_observations>=2 then
      v_confirmed:=array_append(v_confirmed,v_record);
    elsif now()-v_pending.first_missing_at>=interval '12 hours' then
      update public.pending_gis_camera_withdrawals
        set complete_inventory_observations=2,last_missing_at=now()
        where source_key=p_source_key and record_key=v_record;
      v_confirmed:=array_append(v_confirmed,v_record);
    else
      update public.pending_gis_camera_withdrawals
        set last_missing_at=now()
        where source_key=p_source_key and record_key=v_record;
      v_pending_count:=v_pending_count+1;
    end if;
  end loop;

  return jsonb_build_object(
    'confirmed',to_jsonb(v_confirmed),
    'pending',v_pending_count
  );
end;
$confirm_gis_withdrawals$;
revoke all on function public.confirm_gis_camera_withdrawals(text,text[])
  from public,anon,authenticated,service_role;
grant execute on function public.confirm_gis_camera_withdrawals(text,text[])
  to service_role;
comment on table public.pending_gis_camera_withdrawals is
'Private two-pass source-specific observation ledger. Missing individual published camera points are not withdrawn until two independently completed official GIS inventories at least twelve hours apart.';
