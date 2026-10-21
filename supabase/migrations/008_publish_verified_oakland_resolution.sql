-- First narrowly published, primary-source-checked government decision.
-- This is a documented CITY COUNCIL AUTHORIZATION, not evidence of a signed
-- contract, expenditure, installed camera count, or an individual official vote.
-- File 26-0294 was adopted as amended on 2025-12-16. Do not confuse it with
-- earlier, unsuccessful Oakland File 26-0189.

begin;

do $oakland_publication_guard$
begin
  if not exists (
    select 1 from public.agenda_evidence_reviews r
    where r.tenant = 'oakland' and r.matter_id=36866
      and r.review_state in ('source_verified','published')
      and r.verified_vendor_relation='explicit_flock'
      and r.decision_outcome='approved'
      and r.reviewed_primary_source_url=
        'https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357'
      and r.reviewed_at is not null
      and r.reviewed_by is not null
  ) then
    raise exception 'Publication blocked: Oakland 26-0294 did not pass primary-source review';
  end if;
  if exists(
    select 1 from public.sources s
    where s.url='https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357'
      and s.status='rejected'
  ) then
    raise exception 'Publication blocked: Oakland evidence source was rejected';
  end if;
end;
$oakland_publication_guard$;

insert into public.jurisdictions(state_code,name,kind)
values ('CA','Oakland','city')
on conflict(state_code,name,kind) do nothing;

insert into public.agencies(jurisdiction_id,name,official_url)
select j.id,'Oakland Police Department',null
from public.jurisdictions j
where j.state_code='CA' and j.name='Oakland' and j.kind='city'
on conflict(jurisdiction_id,name) do nothing;

insert into public.sources(url,title,publisher,source_type,status)
values (
  'https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357',
  'Oakland City Council File 26-0294: OPD Community Safety Cameras Policy and Flock Agreement',
  'City of Oakland',
  'official_government_legislative_record',
  'verified')
on conflict(url) do update
set title=excluded.title,
    publisher=excluded.publisher,
    status='verified',
    source_type=excluded.source_type
where public.sources.status <> 'rejected';

-- One individually source-reviewed public action, no contract table entry:
-- actual contract execution remains unknown.
insert into public.actions (
  agency_id,jurisdiction_id,action_type,action_date,
  factual_description,recorded_position,source_id,review_status)
select a.id,j.id,'contract_approval','2025-12-16'::date,
  'On December 16, 2025, the Oakland City Council adopted as amended Resolution 26-0294 concerning the Oakland Police Department community safety camera policy and authorization of a two-year Flock Safety ALPR/camera agreement. This records an adopted council authorization, not confirmation of a signed contract or installed cameras.',
  'not_applicable',s.id,'published'
from public.jurisdictions j
join public.agencies a on a.jurisdiction_id=j.id and a.name='Oakland Police Department'
join public.sources s on s.url=
 'https://oakland.legistar.com/LegislationDetail.aspx?GUID=BC9ADFD5-2714-4303-BEA4-70DF1AD489D1&ID=7778357'
where j.name='Oakland' and j.state_code='CA' and j.kind='city'
  and s.status='verified'
  and not exists (
    select 1 from public.actions x
    where x.agency_id=a.id and x.source_id=s.id
      and x.action_type='contract_approval' and x.action_date='2025-12-16'::date
  );

update public.agenda_evidence_reviews
set review_state='published'
where tenant='oakland' and matter_id=36866
  and review_state='source_verified'
  and verified_vendor_relation='explicit_flock'
  and decision_outcome='approved';

update public.discovery_queue q
set status='accepted',
    reviewer_notes='Primary-source reviewed: Oakland File 26-0294 adopted as amended on 2025-12-16. The published item states authorization, not execution.'
from public.agenda_evidence_reviews r
where q.id=r.discovery_queue_id
  and r.tenant='oakland' and r.matter_id=36866
  and r.review_state='published'
  and q.status='in_review';

commit;
