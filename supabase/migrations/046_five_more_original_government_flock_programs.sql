-- 046. Five additional original-government Flock disclosures, reviewed 2026-10-23.
-- Agency statements and vendor use are NOT georeferenced camera GIS points.
-- Do not infer a camera's actual operation from an agency press page.
insert into public.flock_documented_programs(
 program_key,jurisdiction_label,state_code,program_status,official_evidence_url,
 official_claim_summary,source_date,reported_camera_count
) values
('leander_tx','Leander, TX','TX','terminated_at_source_date',
 'https://www.leandertx.gov/995/Flock-FAQ',
 'The City reports that its police department stopped using Flock cameras and Flock data on September 4, 2026 following a City Council decision. The page describes 15 former fixed-location cameras. This is a terminated historical program, not a currently operating deployment.',
 '2026-09-04',null),
('hidden_hills_ca','Hidden Hills, CA','CA','documented_at_source_date',
 'https://hiddenhills.gov/2026/09/30/flock-safety-license-plate-cameras-faq/',
 'The City says it has three Flock ALPR cameras, one at each guard shack, in its September 30, 2026 FAQ. These descriptions do not provide independently surveyed individual camera coordinates or establish real-time operational status.',
 '2026-09-30',3),
('la_canada_flintridge_ca','La Cañada Flintridge, CA','CA','documented_at_source_date',
 'https://lcf.ca.gov/public-safety/flock-alpr-public-safety-cameras/',
 'The City describes a Flock Safety ALPR program administered by the Los Angeles County Sheriff’s Department and states that cameras are positioned at city entry/exit roads and other strategic locations. No independently verified GIS camera coordinates or current camera status are supplied.',
 '2026-09-29',null),
('prosper_tx','Prosper, TX','TX','documented_at_source_date',
 'https://www.prospertx.gov/748/Technology-Transparency',
 'The Town Police Department says it uses Flock license plate readers on inbound roads and main thoroughfares, alongside other Flock technologies such as live-feed cameras. This is a documented agency program, not a camera-location inventory or a statement of current uptime.',
 '2026-10-23',null),
('shakopee_mn','Shakopee, MN','MN','documented_at_source_date',
 'https://www.shakopeemn.gov/public_safety/police_department/reports___transparency.php',
 'The Police Department transparency page describes seven ALPR Flock cameras with named intersection-level areas. It separately identifies equipment that is offline, missing, or pending relocation; it does not provide verified current point geometry for seven active readers.',
 '2026-09-10',7)
on conflict(program_key) do nothing;
