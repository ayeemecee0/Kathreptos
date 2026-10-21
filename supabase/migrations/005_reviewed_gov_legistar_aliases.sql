-- Extend the private reviewed government authority registry with explicitly
-- reviewed .gov domain/Legistar aliases. .gov pages remain government websites;
-- this table binds otherwise ambiguous tenant names to actual jurisdictions.
-- Candidate discovery can NEVER approve or alter these reviewed bindings.
alter table public.official_government_domains
  drop constraint official_government_domains_domain_check;
alter table public.official_government_domains
  add constraint official_government_domains_domain_check
  check (domain ~ '^[a-z0-9-]+(\.[a-z0-9-]+)+$'
     and domain ~ '\.(com|org|net|us|gov)$');

-- Both independently identifiable agency websites have official HTML pages
-- that explicitly link their matching Legistar portals. The verifier still
-- fetches each link, verifies the jurisdiction name, and checks the API.
insert into public.official_government_domains
  (domain, jurisdiction_label, legistar_tenant, legistar_evidence_url,
   allow_www, verification_status, evidence_url, reviewed_by, reviewed_at, review_notes)
values
  ('cabq.gov', 'Albuquerque, NM', 'cabq',
   'https://www.cabq.gov/council/news/special-procedures-for-may-17-2021-city-council-meeting',
   true, 'verified',
   'https://www.cabq.gov/council/news/special-procedures-for-may-17-2021-city-council-meeting',
   'Katoptron official government source review', now(),
   'Official City of Albuquerque council notice explicitly links cabq.legistar.com/Calendar.aspx; CABQ is the city municipal abbreviation, not a guessed jurisdiction.'),
  ('cookcountyil.gov', 'Cook County, IL', 'cook-county',
   'https://www.cookcountyil.gov/news/cook-county-board-modifies-2019-schedule-regular-and-consent-calendar-meetings',
   true, 'verified',
   'https://www.cookcountyil.gov/news/cook-county-board-modifies-2019-schedule-regular-and-consent-calendar-meetings',
   'Katoptron official government source review', now(),
   'Official Cook County government news page explicitly links cook-county.legistar.com and identifies Cook County, Illinois.')
on conflict (domain) do nothing;
