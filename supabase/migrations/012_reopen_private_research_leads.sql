-- Permit reversing PRIVATE accepted research leads without administrator SQL.
-- Publicly published factual records remain immutable via reviewer dashboard.
create or replace function public.editorial_general_decide(
  p_id uuid,
  p_action text,
  p_expected_updated_at timestamptz,
  p_topic text default 'unclassified',
  p_vendor text default 'not_assessed',
  p_primary_source text default null,
  p_notes text default null)
returns jsonb language plpgsql security definer
set search_path = ''
as $general_decide$
declare
  v_uid uuid := auth.uid();
  q public.discovery_queue%rowtype;
  g public.editorial_general_reviews%rowtype;
  v_old_status text;
  v_next text;
  v_source text;
  v_event bigint;
begin
  if v_uid is null or not exists (
      select 1 from public.editorial_reviewers where user_id=v_uid and disabled_at is null) then
    raise exception 'Reviewer access required' using errcode='42501';
  end if;
  if p_id is null or p_expected_updated_at is null
      or p_action not in ('save','accept','reject','reopen') then
    raise exception 'Invalid review action or missing revision';
  end if;
  if p_topic not in ('unclassified','flock_contract','flock_policy',
                     'flock_deployment','presentation','general_alpr','irrelevant')
      or p_vendor not in ('not_assessed','explicit_flock',
                           'different_vendor','general_alpr','indeterminate')
      or pg_catalog.length(coalesce(p_notes,''))>5000
      or pg_catalog.length(coalesce(p_primary_source,''))>1400 then
    raise exception 'Invalid classification or text length';
  end if;
  select * into q from public.discovery_queue where id=p_id for update;
  if not found then raise exception 'Queue item not found'; end if;
  if exists(select 1 from public.agenda_evidence_reviews
            where discovery_queue_id=p_id) then
    raise exception 'Use the dedicated government agenda review process';
  end if;
  select * into g from public.editorial_general_reviews
    where discovery_queue_id=p_id for update;
  if coalesce(g.updated_at,q.discovered_at) is distinct from p_expected_updated_at then
    raise exception 'Another reviewer changed this record. Reload before saving';
  end if;
  v_old_status := q.status;
  if p_action='reopen' and q.status not in ('rejected','accepted') then
    raise exception 'Only accepted or rejected research leads can be reopened';
  end if;
  if q.status='accepted' and p_action<>'reopen' then
    raise exception 'Accepted leads are locked. An administrator must reassess them';
  end if;
  if p_action='reject' and nullif(pg_catalog.btrim(coalesce(p_notes,'')),'') is null then
    raise exception 'Explain why this research lead is being rejected';
  end if;
  v_source := nullif(pg_catalog.btrim(coalesce(p_primary_source,'')),'');
  if v_source is not null and (
        v_source !~* '^https://[a-z0-9.-]+(/|$)'
        or v_source ~ '[[:space:]]'
        or v_source ~* '^https://[^/]*@'
        ) then
    raise exception 'Use a valid HTTPS public source URL';
  end if;
  if p_action='accept' and (v_source is null or p_topic='unclassified'
       or p_vendor='not_assessed' or nullif(pg_catalog.btrim(coalesce(p_notes,'')),'') is null) then
    raise exception 'Acceptance requires classification, primary-source link, vendor assessment and notes';
  end if;
  v_next := case p_action when 'reject' then 'rejected'
      when 'accept' then 'accepted' else 'in_review' end;
  insert into public.editorial_general_reviews(
    discovery_queue_id,topic,vendor_relation,primary_source_url,
    reviewed_by,reviewed_at,updated_at)
  values(p_id,p_topic,p_vendor,v_source,
         case when p_action='accept' then v_uid else null end,
         case when p_action='accept' then now() else null end,
         pg_catalog.clock_timestamp())
  on conflict(discovery_queue_id) do update set
     topic=excluded.topic,vendor_relation=excluded.vendor_relation,
     primary_source_url=excluded.primary_source_url,
     reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at,
     updated_at=excluded.updated_at;
  update public.discovery_queue
    set status=v_next,
        reviewer_notes=nullif(pg_catalog.btrim(coalesce(p_notes,'')),'')
    where id=p_id;
  insert into public.editorial_general_events(
    discovery_queue_id,actor_id,event_type,old_status,new_status,details)
    values(p_id,v_uid,p_action,v_old_status,v_next,
           pg_catalog.jsonb_build_object(
             'topic',p_topic,'vendor_relation',p_vendor,'primary_source_url',v_source,
             'notes',p_notes))
    returning id into v_event;
  return pg_catalog.jsonb_build_object(
    'ok',true,'event_id',v_event,'status',v_next);
end;
$general_decide$;
