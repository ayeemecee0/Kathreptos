-- 049: Three additional original-government Flock program disclosures.
-- Program records are narrative historical evidence, never camera GIS
-- coordinates. Source date is the dated council event, or review date for
-- an undated government FAQ. A Council agenda is not an approved contract.
insert into public.flock_documented_programs(
 program_key,jurisdiction_label,state_code,program_status,
 official_evidence_url,official_claim_summary,source_date,
 reported_camera_count
) values
('asheville_nc','Asheville, NC','NC','terminated_at_source_date',
 'https://council-minutes-archive.ashevillenc.gov/Minutes.2026-08-25.html',
 'The City Council adopted Resolution 26-180 on August 25, 2026 by a 5–2 vote instructing the City Manager to terminate Asheville’s Flock Safety agreement and suspend access to its data. Council minutes described eleven City-operated readers before termination. This is a dated termination decision, not proof equipment was physically removed.',
 '2026-08-25',null),
('seabrook_tx','Seabrook, TX','TX','documented_at_source_date',
 'https://www.seabrooktx.gov/m/faq',
 'The Seabrook Police Department official FAQ states it uses Flock Safety technology and identifies eight fixed license-plate reader units with named intersection/roadway locations and facing directions. These textual descriptions are not independently surveyed individual camera-point coordinates or real-time operating records; source reviewed October 23, 2026.',
 '2026-10-23',8),
('newport_beach_ca','Newport Beach, CA','CA','documented_at_source_date',
 'https://newportbeach.legistar.com/LegislationDetail.aspx?GUID=84D5BF30-0671-47C6-939F-5266748FCD6B&ID=7643929&Options=&Search=',
 'The City Council’s September 9, 2025 original Legistar agenda item proposed Amendment Two to an existing Flock automated license plate reader contract, including four additional ALPR units and revised retention terms. The publicly indexed agenda does not itself prove this amendment passed or establish surveyed camera locations.',
 '2025-09-09',null)
on conflict(program_key) do nothing;
