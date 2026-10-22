-- Documented Flock agency records WITHOUT claiming coordinates.
-- A government program may be verified while no individual camera position is.
-- Program status is relative to the dated official source, never 'open now'.
create table if not exists public.flock_documented_programs (
  program_key text primary key check(program_key ~ '^[a-z0-9_-]{5,70}$'),
  jurisdiction_label text not null check(length(jurisdiction_label) between 5 and 150),
  state_code text not null check(state_code ~ '^[A-Z]{2}$'),
  program_status text not null check(program_status in
    ('documented_at_source_date','terminated_at_source_date')),
  official_evidence_url text not null check(
    official_evidence_url ~ '^https://[A-Za-z0-9.-]+/' and length(official_evidence_url)<2000),
  official_claim_summary text not null check(length(official_claim_summary) between 35 and 1000),
  source_date date not null,
  reported_camera_count integer check(reported_camera_count between 0 and 10000),
  record_status text not null default 'verified'
    check(record_status in ('verified','withdrawn')),
  reviewed_at timestamptz not null default now(),
  check(source_date<=current_date)
);
alter table public.flock_documented_programs enable row level security;
revoke all on public.flock_documented_programs from public,anon,authenticated,service_role;
grant select on public.flock_documented_programs to anon,authenticated;
create policy only_verified_flock_programs on public.flock_documented_programs
 for select to anon,authenticated using(record_status='verified');
comment on table public.flock_documented_programs is
'Original-government Flock program claims, including terminated programs, with NO point geometry. Never infer exact cameras, location, current operation or live ALPR observations.';

insert into public.flock_documented_programs (
program_key,jurisdiction_label,state_code,program_status,official_evidence_url,
official_claim_summary,source_date,reported_camera_count
) values
('south_portland_me','South Portland, ME','ME','documented_at_source_date',
 'https://southportland.gov/m/newsflash',
 'The City news page describes seven stationary Flock cameras and approximate road-area placements. Precise point geometry is not documented by this source, so no individual camera pins are published.',
 '2026-07-01',7),
('provo_ut','Provo, UT','UT','documented_at_source_date',
 'https://www.provo.gov/m/newsflash/Home/Detail/225',
 'The City transparency page confirms its Flock Safety ALPR contract and says deployment began in 2023. This claim does not provide verified individual camera coordinates.',
 '2026-10-01',null),
('league_city_tx','League City, TX','TX','documented_at_source_date',
 'https://www.leaguecitytx.gov/m/newsflash/Archive/Item/6287?arcId=15008',
 'The Police Department reported 55 active Flock cameras and 16 awaiting TxDOT permits as of its July 24, 2026 public notice. This is a dated agency claim, NOT current uptime verification or a camera location inventory.',
 '2026-07-24',55),
('perry_ga','Perry, GA','GA','documented_at_source_date',
 'https://www.perry-ga.gov/flock-camera-system',
 'The City Police Department official page describes its Flock Safety camera system. The page does not establish independently georeferenced camera positions.',
 '2026-10-22',null),
('los_altos_hills_ca','Los Altos Hills, CA','CA','terminated_at_source_date',
 'https://www.losaltoshills.ca.gov/455/Automatic-License-Plate-Readers-ALPR',
 'The Town announces its January 15, 2026 vote to terminate its Flock Safety contract, with cameras to go offline immediately and removal in progress. This record must never be displayed as a currently active deployment.',
 '2026-01-15',null)
on conflict(program_key) do nothing;
