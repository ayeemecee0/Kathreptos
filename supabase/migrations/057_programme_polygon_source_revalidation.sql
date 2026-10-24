-- 057: Original governmental programme polygon records are source-bound.
-- Live link changes can withdraw areas without exposing mutable camera data.
-- Outages and unchanged pages are NOT removal evidence.

grant select on public.flock_documented_coverage_areas to service_role;

create table if not exists public.programme_flock_polygon_evidence_history (
 id bigint generated always as identity primary key,
 area_key text not null references public.flock_documented_coverage_areas(area_key),
 original_page_sha256 text not null check(original_page_sha256 ~ '^[a-f0-9]{64}$'),
 current_page_sha256 text not null check(current_page_sha256 ~ '^[a-f0-9]{64}$'),
 observed_at timestamptz not null default now(),
 check(original_page_sha256<>current_page_sha256)
);
create index if not exists programme_polygon_evidence_history_area_idx
 on public.programme_flock_polygon_evidence_history(area_key,observed_at desc);
alter table public.programme_flock_polygon_evidence_history enable row level security;
revoke all on public.programme_flock_polygon_evidence_history
 from public,anon,authenticated,service_role;

create or replace function public.log_programme_area_page_revision()
returns trigger language plpgsql security definer set search_path=''
as $area_revision$
begin
 if old.government_program_key is not null and
   old.government_page_sha256 is distinct from new.government_page_sha256 then
   insert into public.programme_flock_polygon_evidence_history
     (area_key,original_page_sha256,current_page_sha256)
   values(new.area_key,old.government_page_sha256,new.government_page_sha256);
 end if;
 return new;
end;
$area_revision$;
revoke all on function public.log_programme_area_page_revision()
 from public,anon,authenticated,service_role;
drop trigger if exists programme_area_original_page_revision
 on public.flock_documented_coverage_areas;
create trigger programme_area_original_page_revision
 after update of government_page_sha256 on public.flock_documented_coverage_areas
 for each row execute function public.log_programme_area_page_revision();

-- Identical original GIS layer/geometry may be rechecked after the
-- government page changes unrelated text. Preserve a private digest history.
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
      set evidence_verified_at=now(),
          government_page_sha256=excluded.government_page_sha256
      where flock_documented_coverage_areas.government_program_key=
           excluded.government_program_key
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

-- Whitelisted, source-specific withdrawal of an original government polygon
-- after a successfully fetched, CHANGED government programme source page
-- removes the exact original polygon GIS-layer hyperlink.
create or replace function public.withdraw_programme_area_after_link_loss(
 p_area_key text,p_current_original_page_sha256 text
) returns boolean language plpgsql security definer set search_path=''
as $area_endorsement_loss$
declare
  a public.flock_documented_coverage_areas%rowtype;
begin
  if p_area_key is null or p_area_key !~ '^area_[a-z0-9_]{8,75}$'
    or p_current_original_page_sha256 !~ '^[a-f0-9]{64}$' then
    raise exception 'Invalid original government polygon withdrawal evidence';
  end if;
  select * into a from public.flock_documented_coverage_areas
  where area_key=p_area_key for update;
  if a.area_key is null or a.government_program_key is null
    or a.geometry_status<>'verified'
    or a.government_page_sha256=p_current_original_page_sha256
  then
    raise exception 'Original government polygon cannot be withdrawn from unchanged or unverified evidence';
  end if;
  update public.flock_documented_coverage_areas
    set geometry_status='withdrawn'
    where area_key=p_area_key and geometry_status='verified';
  return true;
end;
$area_endorsement_loss$;
revoke all on function public.withdraw_programme_area_after_link_loss(text,text)
 from public,anon,authenticated,service_role;
grant execute on function public.withdraw_programme_area_after_link_loss(text,text)
 to service_role;

create or replace function public.withdraw_programme_polygons_when_status_ends()
returns trigger language plpgsql security definer set search_path=''
as $programme_end$
begin
 if old.record_status='verified' and
    old.program_status='documented_at_source_date' and
    (new.record_status<>'verified' or
     new.program_status<>'documented_at_source_date') then
   update public.flock_documented_coverage_areas
     set geometry_status='withdrawn'
     where government_program_key=new.program_key and geometry_status='verified';
 end if;
 return new;
end;
$programme_end$;
revoke all on function public.withdraw_programme_polygons_when_status_ends()
 from public,anon,authenticated,service_role;
drop trigger if exists withdraw_programme_polygon_after_parent_status_end
 on public.flock_documented_programs;
create trigger withdraw_programme_polygon_after_parent_status_end
 after update of record_status,program_status on public.flock_documented_programs
 for each row execute function public.withdraw_programme_polygons_when_status_ends();
