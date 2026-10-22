-- Data-driven GIS verification policies and auditable camera evidence history.
-- Only database-owner-reviewed government sources receive active profiles.
create table if not exists public.gis_verification_profiles (
  source_key text primary key references public.trusted_flock_gis_sources(source_key),
  expected_layer_name text,
  identity_mode text not null check (identity_mode in ('per_feature_vendor','official_flock_layer')),
  vendor_field text,
  camera_id_field text,
  service_evidence_mode text not null check
    (service_evidence_mode in ('explicit_flock_service_text','listed_flock_layer','official_program_plus_vendor')),
  profile_status text not null check(profile_status in ('verified','revoked')),
  reviewed_at timestamptz not null default now(),
  review_basis text not null check(length(btrim(review_basis))>=60),
  check (
   (identity_mode='per_feature_vendor' and vendor_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$')
   or (identity_mode='official_flock_layer' and
       expected_layer_name ~* '^flock[_ ]cameras$' and
       camera_id_field ~ '^[A-Za-z][A-Za-z0-9_]{1,50}$')
  )
);
insert into public.gis_verification_profiles(source_key,expected_layer_name,identity_mode,
 vendor_field,camera_id_field,service_evidence_mode,profile_status,review_basis)
values
 ('monroe_wa',null,'per_feature_vendor','CameraType',null,'official_program_plus_vendor',
 'verified','Independently reviewed Monroe WA municipal Camera Systems points. Only feature rows explicitly saying Flock ALPR qualify; city Flock Safety program corroborates vendor.'),
 ('elpaso_co','Flock_Cameras','official_flock_layer',null,'NAME','explicit_flock_service_text',
 'verified','El Paso County CO official Sheriff service explicitly says Flock and camera/CCTV in service metadata, with official Flock_Cameras point layer. Require named features.'),
 ('peoria_az','Flock Cameras','official_flock_layer',null,'CameraID','listed_flock_layer',
 'verified','Peoria AZ city Public Works official MapServer lists exact Flock Cameras layer with CameraID and Location attributes; government GIS was independently reviewed.')
on conflict(source_key) do nothing;
alter table public.gis_verification_profiles enable row level security;
revoke all on public.gis_verification_profiles from public,anon,authenticated,service_role;
grant select on public.gis_verification_profiles to service_role;

create table if not exists public.flock_camera_evidence_history (
  id bigint generated always as identity primary key,
  record_key text not null references public.flock_camera_locations(record_key),
  event_type text not null check (event_type in ('published','withdrawn','source_rechecked')),
  recorded_at timestamptz not null default now(),
  source_url text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[a-f0-9]{64}$')
);
create index if not exists flock_camera_history_record_idx
 on public.flock_camera_evidence_history(record_key,recorded_at desc);
alter table public.flock_camera_evidence_history enable row level security;
revoke all on public.flock_camera_evidence_history from public,anon,authenticated,service_role;
grant select on public.flock_camera_evidence_history to anon,authenticated;
-- Never expose history for withdrawn/unsupported cameras as if they were current.
create policy active_camera_history_only on public.flock_camera_evidence_history
for select to anon,authenticated
using (exists (
  select 1 from public.flock_camera_locations c
   where c.record_key=flock_camera_evidence_history.record_key
    and c.verification_status='verified'
));
-- The trigger needs owner privileges; direct user roles cannot write history.
create or replace function public.log_verified_camera_history()
returns trigger language plpgsql security definer set search_path=''
as $$
begin
 if tg_op='INSERT' then
  insert into public.flock_camera_evidence_history
    (record_key,event_type,recorded_at,source_url,evidence_sha256)
  values(new.record_key,'published',new.published_at,new.source_url,new.evidence_sha256);
 elsif old.verification_status <> new.verification_status and new.verification_status='revoked' then
  insert into public.flock_camera_evidence_history
    (record_key,event_type,source_url,evidence_sha256)
  values(new.record_key,'withdrawn',new.source_url,new.evidence_sha256);
 elsif new.last_source_recheck_at > old.last_source_recheck_at then
  insert into public.flock_camera_evidence_history
    (record_key,event_type,source_url,evidence_sha256)
  values(new.record_key,'source_rechecked',new.source_url,new.evidence_sha256);
 end if;
 return new;
end;
$$;
revoke all on function public.log_verified_camera_history() from public,anon,authenticated;
drop trigger if exists verified_camera_evidence_history on public.flock_camera_locations;
create trigger verified_camera_evidence_history
after insert or update on public.flock_camera_locations
for each row execute function public.log_verified_camera_history();
insert into public.flock_camera_evidence_history(record_key,event_type,recorded_at,source_url,evidence_sha256)
select c.record_key,'published',c.published_at,c.source_url,c.evidence_sha256
from public.flock_camera_locations c
where not exists (
 select 1 from public.flock_camera_evidence_history h
 where h.record_key=c.record_key and h.event_type='published'
);
comment on table public.gis_verification_profiles is
'Owner-approved per-source verification rules. A program may operate on new sources without Python edits once source root and policy are independently reviewed; untrusted discovery cannot grant profiles.';
comment on table public.flock_camera_evidence_history is
'Append-only server-side publication and recheck events; public SELECT only for currently verified camera records.';
