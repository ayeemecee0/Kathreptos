-- 054: Original-government Flock program notices with dated, precise status.
-- Dated source claims ONLY. No georeferenced camera points or assumed
-- live operation. A vote to terminate *some* devices is not a full closure.
insert into public.flock_documented_programs(
 program_key,jurisdiction_label,state_code,program_status,
 official_evidence_url,official_claim_summary,source_date,
 reported_camera_count,record_status
) values
('henrico_county_va','Henrico County, VA','VA','documented_at_source_date',
 'https://henrico.gov/news/2026/10/henrico-police-to-eliminate-flock-cameras/',
 'Henrico County said on October 6, 2026 that its Police Division intended to terminate the Flock Safety ALPR contract within seven days due to privacy concerns. The published announcement does not itself confirm the later termination or physical camera removal.',
 '2026-10-06',null,'verified'),
('panama_city_fl','Panama City, FL','FL','documented_at_source_date',
 'https://panamacity.gov/m/newsflash/home/detail/811',
 'On September 8, 2026 the City Commission voted to terminate and remove 41 Flock ALPR cameras in Florida state rights-of-way; a separate plan for its remaining city cameras was still requested. The 41 are a partial-device count, not total active coverage or proof removal had occurred.',
 '2026-09-08',null,'verified'),
('lafayette_co','Lafayette, CO','CO','documented_at_source_date',
 'https://www.lafayetteco.gov/m/newsflash/home/detail/10277',
 'An October 22, 2026 municipal statement says Lafayette approved its 2027 budget without Flock funding, directed immediate cessation of Flock use, and began early contract termination and camera covering. Thirty devices were part of the city contract; completion of physical removal was not established.',
 '2026-10-22',30,'verified'),
('elgin_tx','Elgin, TX','TX','terminated_at_source_date',
 'https://www.elgintexas.gov/m/newsflash/home/detail/1855',
 'An October 15, 2026 city council summary says the October 13 council voted to end Elgin City association with Flock Safety for ALPR cameras after police had already paused their use in September. This confirms the municipal decision, not removal of every device.',
 '2026-10-15',null,'verified'),
('liberty_hill_tx','Liberty Hill, TX','TX','terminated_at_source_date',
 'https://www.libertyhilltx.gov/m/newsflash/home/detail/395',
 'The September 17, 2026 city notice confirms council voted 7-0 on September 9 to end municipal Flock ALPR use and reports city staff removed all cameras under that specific city program on September 15. It does not cover unrelated private or other-agency cameras.',
 '2026-09-17',null,'verified'),
('poughkeepsie_ny','Poughkeepsie, NY','NY','documented_at_source_date',
 'https://www.cityofpoughkeepsie.gov/m/newsflash/Home/Detail/417',
 'In an October 22, 2026 statement, the mayor said she intended to veto a Common Council measure that would end municipal Flock Safety technologies and discussed existing police ALPR use. Intention to veto is not proof the veto was subsequently issued or the program continued unchanged.',
 '2026-10-22',null,'verified'),
('las_cruces_nm','Las Cruces, NM','NM','documented_at_source_date',
 'https://lascruces.gov/lcpd-provides-video-transparency-portal-on-flock-cameras/',
 'The City of Las Cruces announced September 15, 2026 that its Police Department used Flock Safety ALPR cameras and introduced a public camera-usage transparency portal. The news release supplies no independently surveyed individual camera coordinates.',
 '2026-09-15',null,'verified')
on conflict(program_key) do nothing;
