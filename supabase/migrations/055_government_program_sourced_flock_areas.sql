-- 055: Independently sourced Flock deployment polygons may come from an
-- original government PROGRAM, even where NO camera GPS points are published.
-- Distinguish the two independent provenance channels explicitly.
alter table public.flock_documented_coverage_areas
 alter column government_source_key drop not null;
alter table public.flock_documented_coverage_areas
 add column if not exists government_program_key text
   references public.flock_documented_programs(program_key);
alter table public.flock_documented_coverage_areas
 add column if not exists government_page_sha256 text
   check(government_page_sha256 is null or
         government_page_sha256 ~ '^[a-f0-9]{64}$');
alter table public.flock_documented_coverage_areas
 add constraint coverage_one_original_source_only
   check(num_nonnulls(government_source_key,government_program_key)=1);
alter table public.flock_documented_coverage_areas
 add constraint coverage_program_original_page_hash
   check(government_program_key is null or government_page_sha256 ~ '^[a-f0-9]{64}$');
create index if not exists coverage_areas_gov_program_idx
 on public.flock_documented_coverage_areas(government_program_key);

drop policy if exists original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas;
create policy original_gov_coverage_areas_only
 on public.flock_documented_coverage_areas for select to anon,authenticated
 using(
   geometry_status='verified' and (
     (government_source_key is not null and exists(
       select 1 from public.trusted_flock_gis_sources s
       where s.source_key=government_source_key and s.source_status='verified'))
     or
     (government_program_key is not null and exists(
       select 1 from public.flock_documented_programs p
       where p.program_key=government_program_key
         and p.record_status='verified'
         and p.program_status='documented_at_source_date'))
   )
 );

-- The original governmental programme and exact same-apex government GIS
-- hyperlink are independently re-fetched by the backend verifier. This RPC
-- protects against accidental ingestion from an arbitrary ESRI account,
-- a non-government webpage, a terminated programme, fake circles, malformed
-- polygon rings and silent source revisions.
create or replace function public.register_government_program_flock_area(
 p_program_key text,p_layer_url text,p_area_key text,p_area_label text,
 p_polygon_sha256 text,p_original_page_sha256 text,p_outline jsonb
) returns boolean language plpgsql security definer set search_path=''
as $original_program_polygon$
declare
  prog public.flock_documented_programs%rowtype;
  page_host text;
  layer_host text;
  firstp jsonb;
  lastp jsonb;
  point jsonb;
  lat double precision;
  lon double precision;
  south double precision:=90;
  north double precision:=-90;
  east double precision:=-180;
  west double precision:=180;
  inserted integer;
begin
  select * into prog from public.flock_documented_programs
    where program_key=p_program_key and record_status='verified'
      and program_status='documented_at_source_date';
  page_host:=split_part(split_part(prog.official_evidence_url,'https://',2),'/',1);
  layer_host:=split_part(split_part(p_layer_url,'https://',2),'/',1);
  if prog.program_key is null
     or p_program_key !~ '^[a-z0-9_]{5,80}$'
     or p_area_key !~ '^area_[a-z0-9_]{8,75}$'
     or length(p_area_label) not between 5 and 160
     or p_polygon_sha256 !~ '^[a-f0-9]{64}$'
     or p_original_page_sha256 !~ '^[a-f0-9]{64}$'
     or prog.official_evidence_url !~ '^https://([a-z0-9-]+\.)+gov/.+'
     or p_layer_url !~ '^https://([a-z0-9-]+\.)+gov/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'
     or array_to_string((string_to_array(page_host,'.'))[
         greatest(array_length(string_to_array(page_host,'.'),1)-1,1):],'.')
       <> array_to_string((string_to_array(layer_host,'.'))[
         greatest(array_length(string_to_array(layer_host,'.'),1)-1,1):],'.')
  then
    raise exception 'Original government Flock programme-to-polygon authority is not independently verified';
  end if;
  if jsonb_typeof(p_outline)<>'array'
     or jsonb_array_length(p_outline) not between 4 and 250
     or p_outline->0 <> p_outline->(jsonb_array_length(p_outline)-1) then
    raise exception 'Original government polygon must contain a closed ring';
  end if;
  for point in select value from jsonb_array_elements(p_outline) as value loop
    if jsonb_typeof(point)<>'array' or jsonb_array_length(point)<>2
      or jsonb_typeof(point->0)<>'number'
      or jsonb_typeof(point->1)<>'number' then
      raise exception 'Original government polygon coordinate is malformed';
    end if;
    lon:=(point->>0)::double precision;
    lat:=(point->>1)::double precision;
    if lon not between -180 and -64 or lat not between 17 and 72 then
      raise exception 'Original government deployment geometry outside US';
    end if;
    south:=least(south,lat);north:=greatest(north,lat);
    west:=least(west,lon);east:=greatest(east,lon);
  end loop;
  if north-south>2.5 or east-west>2.5
     or (select count(distinct value)
         from jsonb_array_elements(p_outline) as value)<3 then
    raise exception 'Original deployment polygon is implausible or degenerate';
  end if;

  insert into public.flock_documented_coverage_areas(
    area_key,government_program_key,government_page_sha256,
    jurisdiction_label,area_label,outline_lonlat,evidence_url,
    evidence_sha256,evidence_summary,geometry_status
  ) values(
    p_area_key,p_program_key,p_original_page_sha256,
    prog.jurisdiction_label,p_area_label,p_outline,p_layer_url,
    p_polygon_sha256,
    'A directly linked, original government Flock-specific GIS polygon documents the dated programme deployment AREA, not any individual camera coordinates. No operational status, uptime, exact device positions or plate detections are established.',
    'verified'
  ) on conflict(area_key) do update
      set evidence_verified_at=now()
      where flock_documented_coverage_areas.government_program_key=
           excluded.government_program_key
        and flock_documented_coverage_areas.government_page_sha256=
           excluded.government_page_sha256
        and flock_documented_coverage_areas.evidence_url=excluded.evidence_url
        and flock_documented_coverage_areas.evidence_sha256=excluded.evidence_sha256
        and flock_documented_coverage_areas.outline_lonlat=excluded.outline_lonlat
        and flock_documented_coverage_areas.geometry_status='verified';
  get diagnostics inserted=row_count;
  if inserted<>1 then
    raise exception 'Original government programme polygon identity changed; do not silently overwrite evidence';
  end if;
  return true;
end;
$original_program_polygon$;
revoke all on function public.register_government_program_flock_area(
 text,text,text,text,text,text,jsonb)
 from public,anon,authenticated,service_role;
grant execute on function public.register_government_program_flock_area(
 text,text,text,text,text,text,jsonb) to service_role;
comment on table public.flock_documented_coverage_areas is
'Public only when independently verified against a live government camera GIS source OR an original active-at-source-date government programme with directly sourced Flock polygon geometry. No inferred city boundaries or fake camera-radius coverage.';
