-- Review and reject the rest of the discovery queue (articles and official
-- government candidate links) WITHOUT automatically publishing them.
-- "Accept research lead" means candidate accepted into private research,
-- not independently verified as a public finding.

create table if not exists public.editorial_general_reviews (
  discovery_queue_id uuid primary key references public.discovery_queue(id) on delete cascade,
  topic text not null default 'unclassified'
    check(topic in ('unclassified','flock_contract','flock_policy','flock_deployment',
                    'presentation','general_alpr','irrelevant')),
  vendor_relation text not null default 'not_assessed'
    check(vendor_relation in ('not_assessed','explicit_flock','different_vendor',
                              'general_alpr','indeterminate')),
  primary_source_url text check (
    primary_source_url is null or primary_source_url ~ '^https://'),
  reviewed_by uuid references auth.users(id),
  reviewed_at timestamptz,
  updated_at timestamptz not null default now()
);
alter table public.editorial_general_reviews enable row level security;
revoke all on public.editorial_general_reviews from anon, authenticated;

create table if not exists public.editorial_general_events (
  id bigint generated always as identity primary key,
  discovery_queue_id uuid not null references public.discovery_queue(id),
  actor_id uuid not null references auth.users(id),
  event_type text not null check (event_type in ('save','accept','reject','reopen')),
  old_status text not null,
  new_status text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists editorial_general_events_queue_idx
  on public.editorial_general_events(discovery_queue_id,created_at desc);
alter table public.editorial_general_events enable row level security;
revoke all on public.editorial_general_events from anon, authenticated;

create or replace function public.editorial_general_list(
  p_state text default 'all',p_limit integer default 60,p_offset integer default 0)
returns jsonb language plpgsql security definer
set search_path = ''
as $general_list$
declare v_uid uuid := auth.uid(); v_total integer; v_items jsonb;
begin
  if v_uid is null or not exists(
    select 1 from public.editorial_reviewers where user_id=v_uid and disabled_at is null) then
    raise exception 'Reviewer access required' using errcode='42501';
  end if;
  if p_state not in ('all','unreviewed','in_review','accepted','rejected')
     or p_limit is null or p_limit not between 1 and 80
     or p_offset is null or p_offset not between 0 and 20000 then
    raise exception 'Invalid general queue pagination';
  end if;
  select count(*)::integer into v_total from public.discovery_queue q
    where (p_state='all' or q.status=p_state)
      and not exists (select 1 from public.agenda_evidence_reviews r
                      where r.discovery_queue_id=q.id);
  select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(t)), '[]'::jsonb)
    into v_items
    from (
      select q.id,q.headline,q.publisher,q.url,q.snippet,q.state_hint,
             q.status,q.reviewer_notes,q.discovered_at,
             g.topic,g.vendor_relation,g.primary_source_url,g.reviewed_at,g.reviewed_by,
             coalesce(g.updated_at,q.discovered_at) as updated_at
      from public.discovery_queue q
      left join public.editorial_general_reviews g on g.discovery_queue_id=q.id
      where (p_state='all' or q.status=p_state)
        and not exists (select 1 from public.agenda_evidence_reviews r
                        where r.discovery_queue_id=q.id)
      order by case q.status when 'unreviewed' then 0
               when 'in_review' then 1 when 'accepted' then 2 else 3 end,
               q.discovered_at desc
      limit p_limit offset p_offset
    ) t;
  return pg_catalog.jsonb_build_object('total',v_total,'items',v_items);
end;
$general_list$;

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
  if p_action='reopen' and q.status<>'rejected' then
    raise exception 'Only rejected research leads can be reopened';
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

create or replace function public.editorial_history(p_id uuid,p_kind text default 'agenda')
returns jsonb language plpgsql security definer
set search_path = ''
as $editorial_history$
declare v_uid uuid := auth.uid(); v_result jsonb;
begin
  if v_uid is null or not exists(select 1 from public.editorial_reviewers
      where user_id=v_uid and disabled_at is null) then
    raise exception 'Reviewer access required' using errcode='42501';
  end if;
  if p_kind='agenda' then
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x)), '[]'::jsonb)
      into v_result from (
      select event_type,old_state,new_state,actor_id,created_at,details
      from public.editorial_review_events where review_id=p_id
      order by created_at desc limit 25) x;
  elsif p_kind='general' then
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x)), '[]'::jsonb)
      into v_result from (
      select event_type,old_status as old_state,new_status as new_state,
             actor_id,created_at,details
      from public.editorial_general_events where discovery_queue_id=p_id
      order by created_at desc limit 25) x;
  else raise exception 'Invalid review type';
  end if;
  return v_result;
end;
$editorial_history$;

revoke all on function public.editorial_general_list(text,integer,integer) from public,anon;
revoke all on function public.editorial_general_decide(
  uuid,text,timestamptz,text,text,text,text) from public,anon;
revoke all on function public.editorial_history(uuid,text) from public,anon;
grant execute on function public.editorial_general_list(text,integer,integer) to authenticated;
grant execute on function public.editorial_general_decide(
  uuid,text,timestamptz,text,text,text,text) to authenticated;
grant execute on function public.editorial_history(uuid,text) to authenticated;
