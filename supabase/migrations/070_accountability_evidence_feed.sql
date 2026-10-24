-- 070: Live, source-backed accountability feed; no inferred votes/contracts.
create or replace view public.flock_accountability_events with (security_invoker=true) as
select ('program:'||p.program_key)::text event_key,'government_program'::text event_type,
(case when p.program_status='terminated_at_source_date' then 'historical_termination' else 'dated_program_disclosure' end)::text evidence_level,
p.jurisdiction_label::text jurisdiction_label,p.state_code::text state_code,
null::text agency_label,null::text person_label,null::text person_role,
p.source_date::date event_date,'government_source_date'::text date_basis,
('Flock program: '||replace(p.program_status,'_',' '))::text title,
p.official_claim_summary::text summary,p.official_evidence_url::text source_url,
'Original government program record'::text source_label,null::numeric amount_usd,p.reported_camera_count::integer camera_count
from public.flock_documented_programs p
where p.record_status='verified' and p.official_evidence_url like 'https://%'
union all
select ('action:'||a.id::text)::text,'editorially_reviewed_action'::text,
(case when a.action_date is null then 'undated_action_description' else 'dated_editorial_action' end)::text,
(coalesce(j.name,ag.name,'Agency not specified')||coalesce(', '||j.state_code,''))::text,j.state_code::text,ag.name::text,
(case when a.person_id is not null and a.recorded_position not in ('not_applicable','unknown') then p.name else null end)::text,
(case when a.person_id is not null and a.recorded_position not in ('not_applicable','unknown') then p.role_title else null end)::text,
a.action_date::date,(case when a.action_date is null then 'not_documented' else 'recorded_action_date' end)::text,
(case when a.action_date is null then 'Government disclosure' else 'Recorded agency action' end)::text,
a.factual_description::text,s.url::text,coalesce(s.title,'Original source')::text,null::numeric,null::integer
from public.published_actions a join public.sources s on s.id=a.source_id and s.status='verified' and s.url like 'https://%'
left join public.agencies ag on ag.id=a.agency_id
left join public.jurisdictions j on j.id=coalesce(a.jurisdiction_id,ag.jurisdiction_id)
left join public.people p on p.id=a.person_id where a.review_status='published'
union all
select ('contract:'||c.id::text)::text,'executed_contract'::text,'editorially_verified_signed_agreement'::text,
(coalesce(j.name,ag.name,'Agency not specified')||coalesce(', '||j.state_code,''))::text,j.state_code::text,ag.name::text,
null::text,null::text,c.signed_on::date,'documented_signature_date'::text,
('Signed Flock agreement: '||coalesce(c.contract_number,'reference not supplied'))::text,
c.summary::text,s.url::text,coalesce(s.title,'Original contract evidence')::text,c.amount_usd::numeric,null::integer
from public.published_contracts c join public.sources s on s.id=c.source_id and s.status='verified' and s.url like 'https://%'
left join public.agencies ag on ag.id=c.agency_id left join public.jurisdictions j on j.id=ag.jurisdiction_id
where c.review_status='published' and c.signed_on is not null and c.vendor ilike '%flock%'
union all
select ('deployment:'||d.id::text)::text,'agency_reported_deployment'::text,'documented_deployment_claim'::text,
(coalesce(j.name,ag.name,'Agency not specified')||coalesce(', '||j.state_code,''))::text,j.state_code::text,ag.name::text,
null::text,null::text,d.as_of_date::date,
(case when d.as_of_date is null then 'as_of_date_not_documented' else 'government_reported_as_of_date' end)::text,
'Agency-reported camera deployment'::text,
('Government-reported program; status: '||coalesce(d.status,'not supplied')||'; location: '||coalesce(d.geography_label,'not specified')||'. A reported camera count does not identify camera coordinates.')::text,
s.url::text,coalesce(s.title,'Government source')::text,null::numeric,d.camera_count::integer
from public.published_deployments d join public.sources s on s.id=d.source_id and s.status='verified' and s.url like 'https://%'
left join public.agencies ag on ag.id=d.agency_id left join public.jurisdictions j on j.id=ag.jurisdiction_id
where d.review_status='published'
union all
select ('agenda:'||m.tenant||':'||m.matter_id::text)::text,'agenda_mention'::text,'original_government_agenda_mention_only'::text,
m.jurisdiction_label::text,substring(m.jurisdiction_label from ', ([A-Z]{2})$')::text,
null::text,null::text,null::text,m.intro_date::date,'matter_introduction_date'::text,
('Official Flock agenda: '||coalesce(m.file_number,m.matter_id::text))::text,
('Original agenda title: '||m.matter_title||'. This does not prove approval, signing, expenditure, installation, or any individual vote.')::text,
m.official_api_url::text,'Exact official Legistar API matter'::text,null::numeric,null::integer
from public.verified_flock_agenda_mentions m where m.status='verified' and m.official_api_url like 'https://%'
union all
select ('decision:'||x.tenant||':'||x.matter_id::text||':'||x.history_id::text)::text,
'recorded_legislative_decision'::text,'verified_governing_body_action'::text,
x.jurisdiction_label::text,substring(x.jurisdiction_label from ', ([A-Z]{2})$')::text,
x.action_body::text,null::text,null::text,x.action_date::date,'official_history_action_date'::text,
('Legislative decision: '||x.action_name)::text,
('Government record outcome: '||x.decision_outcome||'. Matter: '||x.matter_title||'. This does not establish any named individual vote, signed contract or deployment.')::text,
x.official_history_url::text,'Exact official action history'::text,null::numeric,null::integer
from public.verified_flock_legislative_decisions x where x.status='verified' and x.official_history_url like 'https://%'
union all
select ('attachment:'||d.tenant||':'||d.matter_id::text||':'||d.attachment_id::text)::text,
'contract_form_document'::text,'document_exists_execution_unverified'::text,
d.jurisdiction_label::text,substring(d.jurisdiction_label from ', ([A-Z]{2})$')::text,
null::text,null::text,null::text,null::date,'document_date_not_established'::text,
('Official agreement-form PDF: '||d.attachment_name)::text,
('Original PDF names Flock Safety and contains agreement-form language. Execution is NOT verified. Related matter: '||d.matter_title)::text,
d.document_url::text,'Original government-hosted document'::text,null::numeric,null::integer
from public.official_flock_contract_documents d where d.status='verified' and d.document_url like 'https://%';
revoke all on public.flock_accountability_events from public,anon,authenticated,service_role;
grant select on public.flock_accountability_events to anon,authenticated,service_role;
comment on view public.flock_accountability_events is 'Caller-RLS-filtered, evidence-tiered Flock government accountability. Agenda mention, source-dated program, legislative decision, documented deployment, contract-form and signed agreement remain distinct.';
