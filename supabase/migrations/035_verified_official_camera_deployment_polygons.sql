-- 035 - True original-government deployment area geometry, when available.
-- Polygon coordinates must come from government-authenticated Flock-specific
-- GIS polygon sources, not a fabricated radius around a city/program record.
create table if not exists public.flock_documented_coverage_areas (
 area_key text primary key check(area_key ~ '^area_[a-z0-9_]{8,75}$'),
 government_source_key text not null
   references public.trusted_flock_gis_sources(source_key),
 jurisdiction_label text not null check(length(jurisdiction_label) between 5 and 150),
 area_label text not null check(length(area_label) between 5 and 160),
 outline_lonlat jsonb not null check(
   jsonb_typeof(outline_lonlat)='array' and
   jsonb_array_length(outline_lonlat) between 4 and 250),
 evidence_url text not null check (
   evidence_url ~ '^https://[a-z0-9.-]+/.+' and length(evidence_url)<2000),
 evidence_sha256 text not null check(evidence_sha256 ~ '^[a-f0-9]{64}$'),
 evidence_summary text not null check(length(evidence_summary) between 80 and 1000),
 geometry_status text not null check(geometry_status in ('verified','withdrawn')),
 evidence_verified_at timestamptz not null default now(),
 created_at timestamptz not null default now()
);
alter table public.flock_documented_coverage_areas enable row level security;
revoke all on public.flock_documented_coverage_areas from public,anon,authenticated,service_role;
grant select on public.flock_documented_coverage_areas to anon,authenticated;
create policy original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas for select to anon,authenticated
 using(
   geometry_status='verified' and exists(
     select 1 from public.trusted_flock_gis_sources s
     where s.source_key=government_source_key and s.source_status='verified')
 );
create index if not exists coverage_areas_source_idx
 on public.flock_documented_coverage_areas(government_source_key);

create or replace function public.register_original_government_flock_area(
  p_source_key text,p_area_key text,p_label text,p_evidence_url text,
  p_evidence_sha text,p_outline jsonb
) returns boolean language plpgsql security definer set search_path=''
as $government_area$
declare
  s public.trusted_flock_gis_sources%rowtype;
  root public.gis_government_host_authorities%rowtype;
  v jsonb;
  firstp jsonb;
  lastp jsonb;
  lon double precision;
  lat double precision;
begin
  select * into s from public.trusted_flock_gis_sources
   where source_key=p_source_key and source_status='verified';
  select * into root from public.gis_government_host_authorities
   where authority_key=p_source_key and verification_status='verified';
  if s.source_key is null or root.authority_key is null
   or s.jurisdiction_label<>root.jurisdiction_label
   or p_area_key !~ '^area_[a-z0-9_]{8,75}$'
   or length(p_label) not between 5 and 160
   or p_evidence_sha !~ '^[a-f0-9]{64}$'
   or p_evidence_url !~ '^https://[a-z0-9.-]+/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'
   or p_evidence_url not like 'https://' || root.government_gis_host || '/%'
  then
   raise exception 'Approximate area requires a verified original government geometry source';
  end if;
  if jsonb_typeof(p_outline)<>'array' or
     jsonb_array_length(p_outline) not between 4 and 250 then
   raise exception 'Original polygon ring incomplete';
  end if;
  firstp:=p_outline->0;
  lastp:=p_outline->(jsonb_array_length(p_outline)-1);
  if firstp<>lastp then
   raise exception 'Original government polygon ring must close';
  end if;
  for v in select value from jsonb_array_elements(p_outline) as value
  loop
   if jsonb_typeof(v)<>'array' or jsonb_array_length(v)<>2
     or jsonb_typeof(v->0)<>'number' or jsonb_typeof(v->1)<>'number' then
    raise exception 'Malformed source geometry coordinates';
   end if;
   lon:=(v->>0)::double precision;
   lat:=(v->>1)::double precision;
   if lon<root.bounds_west or lon>root.bounds_east or
     lat<root.bounds_south or lat>root.bounds_north then
    raise exception 'Coverage polygon not within independently approved jurisdiction';
   end if;
  end loop;
  if (select count(distinct value) from jsonb_array_elements(p_outline) as value)<3 then
    raise exception 'Polygon requires at least three distinct original coordinates';
  end if;
  insert into public.flock_documented_coverage_areas(
    area_key,government_source_key,jurisdiction_label,area_label,
    outline_lonlat,evidence_url,evidence_sha256,evidence_summary,geometry_status
  ) values(
    p_area_key,p_source_key,s.jurisdiction_label,p_label,
    p_outline,p_evidence_url,p_evidence_sha,
    'The original government-operated Flock-specific GIS polygon documents a deployment area, not a camera location. Boundary geometry comes from the cited original source. Actual cameras may be elsewhere or offline.',
    'verified'
  ) on conflict(area_key) do nothing;
  return true;
end;
$government_area$;
revoke all on function public.register_original_government_flock_area(
 text,text,text,text,text,jsonb) from public,anon,authenticated,service_role;
grant execute on function public.register_original_government_flock_area(
 text,text,text,text,text,jsonb) to service_role;

create or replace function public.withdraw_official_areas_after_source_revocation()
returns trigger language plpgsql security definer set search_path=''
as $area_revoke$
begin
 if old.source_status='verified' and new.source_status<>'verified' then
   update public.flock_documented_coverage_areas
   set geometry_status='withdrawn'
   where government_source_key=new.source_key and geometry_status='verified';
 end if;
 return new;
end;
$area_revoke$;
revoke all on function public.withdraw_official_areas_after_source_revocation()
 from public,anon,authenticated,service_role;
drop trigger if exists withdraw_official_areas_after_source_revocation on public.trusted_flock_gis_sources;
create trigger withdraw_official_areas_after_source_revocation
after update of source_status on public.trusted_flock_gis_sources
for each row execute function public.withdraw_official_areas_after_source_revocation();

comment on table public.flock_documented_coverage_areas is
'Optional source-backed Flock deployment-area polygons only, distinct from verified camera points and from general agency procurement. Empty until original GIS area geometry is independently authenticated.';
