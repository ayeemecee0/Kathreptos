-- Katoptron first verified batch. Idempotent. Public agency-level information only.
-- Sources checked against official agency websites on 2026-10-20.
BEGIN;
INSERT INTO public.jurisdictions(state_code,name,kind) VALUES
('IL','Wilmette','city'),('MN','Shakopee','city'),('MA','Taunton','city')
ON CONFLICT(state_code,name,kind) DO NOTHING;

INSERT INTO public.agencies(jurisdiction_id,name,official_url)
SELECT j.id,v.agency,v.url FROM (VALUES
('IL','Wilmette','Wilmette Police Department','https://www.wilmette.gov/295/Automated-License-Plate-Readers-ALPR'),
('MN','Shakopee','Shakopee Police Department','https://www.shakopeemn.gov/public_safety/police_department/reports___transparency.php'),
('MA','Taunton','Taunton Police Department','https://tauntonpd.com/alpr-transparency-portal/')
) v(state_code,city,agency,url)
JOIN public.jurisdictions j ON j.state_code=v.state_code AND j.name=v.city AND j.kind='city'
ON CONFLICT(jurisdiction_id,name) DO NOTHING;

INSERT INTO public.sources(url,title,publisher,source_type,status) VALUES
('https://www.wilmette.gov/295/Automated-License-Plate-Readers-ALPR','Automated License Plate Readers (ALPR)','Village of Wilmette','official_agency','verified'),
('https://www.shakopeemn.gov/public_safety/police_department/reports___transparency.php','Reports & Transparency','City of Shakopee','official_agency','verified'),
('https://tauntonpd.com/alpr-transparency-portal/','ALPR Transparency Portal','Taunton Police Department','official_agency','verified')
ON CONFLICT(url) DO UPDATE SET status='verified',title=excluded.title,publisher=excluded.publisher,source_type=excluded.source_type;

-- Agency program decisions documented on official public pages. No inferred signing dates or prices.
INSERT INTO public.actions(agency_id,jurisdiction_id,action_type,factual_description,recorded_position,source_id,review_status)
SELECT a.id,j.id,'other',v.description,'not_applicable',s.id,'published'
FROM (VALUES
('IL','Wilmette','Wilmette Police Department','The Village of Wilmette states that it contracted with Flock Safety for an ALPR program and publishes its policy and transparency resources.'),
('MN','Shakopee','Shakopee Police Department','The City of Shakopee publishes its Flock Safety ALPR program resources, including a contract, policy, independent audit information and public portal.'),
('MA','Taunton','Taunton Police Department','The Taunton Police Department publicly describes its Flock Safety ALPR program and provides a link to its current Flock contract.')
) v(state_code,city,agency,description)
JOIN public.jurisdictions j ON j.state_code=v.state_code AND j.name=v.city AND j.kind='city'
JOIN public.agencies a ON a.jurisdiction_id=j.id AND a.name=v.agency
JOIN public.sources s ON s.publisher=CASE v.state_code WHEN 'IL' THEN 'Village of Wilmette' WHEN 'MN' THEN 'City of Shakopee' ELSE 'Taunton Police Department' END
WHERE NOT EXISTS(SELECT 1 FROM public.actions existing WHERE existing.agency_id=a.id AND existing.source_id=s.id AND existing.factual_description=v.description);

-- Shakopee reports seven ALPR cameras; Wilmette's 22-unit figure is an approval target, not confirmed installed count.
-- Counts are agency-reported totals, not camera coordinates or vehicle data.
INSERT INTO public.deployments(agency_id,camera_count,status,geography_label,source_id,review_status)
SELECT a.id,v.camera_count,'reported',v.city,s.id,'published'
FROM (VALUES
('MN','Shakopee','Shakopee Police Department',7,'https://www.shakopeemn.gov/public_safety/police_department/reports___transparency.php')
) v(state_code,city,agency,camera_count,url)
JOIN public.jurisdictions j ON j.state_code=v.state_code AND j.name=v.city AND j.kind='city'
JOIN public.agencies a ON a.jurisdiction_id=j.id AND a.name=v.agency
JOIN public.sources s ON s.url=v.url
WHERE NOT EXISTS(SELECT 1 FROM public.deployments existing WHERE existing.agency_id=a.id AND existing.source_id=s.id AND existing.camera_count=v.camera_count);
COMMIT;
