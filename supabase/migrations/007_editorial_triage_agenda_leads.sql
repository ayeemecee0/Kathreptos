-- First editorial triage of the 16 confirmed, private Legistar matter leads.
-- Triage notes are NOT source verification. Only three source-matched cases
-- below receive a source_verified state; none of these changes publishes data.

begin;

with notes(tenant,matter_id,summary) as (
  values
  ('cabq',13444::bigint,'General ALPR records-retention ordinance; no Flock Safety vendor identified in the queued metadata. Do not label this a Flock contract.'),
  ('commerce',12379,'Flock Safety Safe Cities Program presentation; presentation does not establish procurement approval or a signed contract.'),
  ('commerce',12775,'Flock Safety presentation; queued action history says discussed and closed 2026-04-06. Check the actual presentation before asserting operational deployment.'),
  ('cook-county',80062,'Proposed ALPR technology/services contract names Insight Public Sector as the vendor. Insight could be a reseller; Flock manufacturer not established by current metadata. Do not publish a Flock contract claim without the actual purchase documents.'),
  ('costamesa',2253,'Mobile license-plate-reader camera system report. No Flock brand established by metadata; examine the NCPA quote and agenda report.'),
  ('costamesa',2660,'Flock lease and maintenance item 24-068; city staff recommended authorization. Confirm final council action separately; recommendation alone is not approval.'),
  ('costamesa',3763,'Flock Safety ALPR report and presentation. A report alone does not establish new contract approval.'),
  ('mountainview',8543,'Flock Safety ALPR cameras and proposed policy (earlier city item). Identify council outcome and dates before claiming approval.'),
  ('mountainview',10357,'City council agenda shows an ALPR contract item approved on 2026-02-24; the linked council report discusses Flock. Need precise amended recommendation before creating any contract record.'),
  ('oakland',36521,'Informational report and sharing policy for ALPR, including possible federal access. Not automatically a Flock contract.'),
  ('oakland',36760,'Earlier Flock Safety agreement resolution File 26-0189. Legistar records this earlier proposal as FAILED. Do not treat it as the later council authorization.'),
  ('oakland',36866,'Later Oakland resolution File 26-0294, adopted AS AMENDED on 2025-12-16. Authorizes a Flock Safety agreement; does not alone prove contract execution.'),
  ('oakland',36983,'OPD 2024 surveillance technology annual reports include ALPR. Not proof of a new Flock purchase.'),
  ('oakland',37445,'OPD 2025 surveillance technology annual reports include ALPR. Not proof of a new Flock purchase.'),
  ('seattle',16942,'Seattle ordinance proposal concerning mandatory 60-day pause for police CCTV/ALPR data. No Flock vendor link established.'),
  ('seattle',16959,'Draft legislation on general ALPR data-protection policy, not evidence of a Flock vendor contract.')
)
update public.agenda_evidence_reviews r
set reviewer_notes = n.summary
from notes n
where r.tenant = n.tenant and r.matter_id=n.matter_id
  and r.review_state = 'needs_primary_review'
  and r.reviewer_notes is null;

-- Independently matched public legislative items. These are narrow source
-- claims, not signed-contract, deployment, or individual-vote assertions.
update public.agenda_evidence_reviews
set official_page_url = 'https://costamesa.legistar.com/LegislationDetail.aspx?GUID=83DDFC82-A148-4F71-A8FE-30577AFD0FA6&ID=6576097',
    reviewed_primary_source_url = 'https://costamesa.legistar.com/LegislationDetail.aspx?GUID=83DDFC82-A148-4F71-A8FE-30577AFD0FA6&ID=6576097',
    verified_vendor_relation = 'explicit_flock',
    decision_outcome = 'proposed',
    reviewed_claim = 'Costa Mesa staff report 24-068 recommended a Flock Safety ALPR camera lease and maintenance agreement for the March 19, 2024 council agenda. The available legislation page lists Agenda Ready, not an approved contract.',
    reviewed_by = 'Katoptron primary-source editorial audit',
    reviewed_at = now(),
    review_state = 'source_verified'
where tenant='costamesa' and matter_id=2660
  and review_state='needs_primary_review';

update public.agenda_evidence_reviews
set official_page_url = 'https://oakland.legistar.com/LegislationDetail.aspx?From=RSS&GUID=AB0429C5-392C-4E03-9941-48F2C952BA0A&ID=7704374',
    reviewed_primary_source_url = 'https://oakland.legistar.com/LegislationDetail.aspx?From=RSS&GUID=AB0429C5-392C-4E03-9941-48F2C952BA0A&ID=7704374',
    verified_vendor_relation = 'explicit_flock',
    decision_outcome = 'failed',
    reviewed_claim = 'Oakland File 26-0189 concerning a proposed Flock Safety camera system agreement is listed as Failed. The November 18, 2025 committee recommendation was not adopted; this was not a signed agreement.',
    reviewed_by = 'Katoptron primary-source editorial audit',
    reviewed_at = now(),
    review_state = 'source_verified'
where tenant='oakland' and matter_id=36760
  and review_state='needs_primary_review';

update public.agenda_evidence_reviews
set official_page_url = 'https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357',
    reviewed_primary_source_url = 'https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357',
    verified_vendor_relation = 'explicit_flock',
    decision_outcome = 'approved',
    reviewed_claim = 'On December 16, 2025, the Oakland City Council adopted as amended File 26-0294 concerning authorization of a two-year Flock Safety ALPR/camera agreement. Adoption is not proof that the agreement was signed or that cameras were installed.',
    reviewed_by = 'Katoptron primary-source editorial audit',
    reviewed_at = now(),
    review_state = 'source_verified'
where tenant='oakland' and matter_id=36866
  and review_state='needs_primary_review';

-- Explicitly begin review, but never mark queued items accepted.
update public.discovery_queue q
set status = 'in_review'
from public.agenda_evidence_reviews r
where q.id=r.discovery_queue_id and q.status='unreviewed';

commit;
