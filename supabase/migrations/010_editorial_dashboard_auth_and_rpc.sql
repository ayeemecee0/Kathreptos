-- Private, authenticated Katoptron editorial review dashboard.
-- Static browser UI has ONLY the public Supabase key. All private reads/writes
-- go through tightly scoped SECURITY DEFINER RPCs gated on auth.uid().
-- No user becomes a reviewer merely by signing up.

create table if not exists public.editorial_reviewers (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('reviewer','publisher')),
  granted_at timestamptz not null default now(),
  granted_by text not null check (length(trim(granted_by)) >= 4),
  disabled_at timestamptz
);
alter table public.editorial_reviewers enable row level security;
revoke all on public.editorial_reviewers from anon, authenticated;

create table if not exists public.editorial_review_events (
  id bigint generated always as identity primary key,
  review_id uuid not null references public.agenda_evidence_reviews(discovery_queue_id),
  actor_id uuid not null references auth.users(id),
  event_type text not null check (event_type in ('save','approve','reject','reopen','publish')),
  old_state text not null,
  new_state text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists editorial_review_events_review_idx
  on public.editorial_review_events(review_id, created_at desc);
alter table public.editorial_review_events enable row level security;
revoke all on public.editorial_review_events from anon, authenticated;

alter table public.agenda_evidence_reviews
  add column if not exists action_date date,
  add column if not exists updated_at timestamptz not null default now();

-- Only approved user IDs can read or review private material. Do not grant
-- direct table access: this RPC deliberately exposes a narrow, controlled shape.
create or replace function public.editorial_session()
returns jsonb language plpgsql security definer
set search_path = ''
as $session$
declare
  v_uid uuid := auth.uid();
  v_role text;
begin
  if v_uid is null then
    raise exception 'Authentication required' using errcode='42501';
  end if;
  select role into v_role from public.editorial_reviewers
    where user_id=v_uid and disabled_at is null;
  return pg_catalog.jsonb_build_object(
    'authorized',v_role is not null,
    'role',v_role,
    'user_id',v_uid);
end;
$session$;

create or replace function public.editorial_list(
  p_state text default 'all',
  p_limit integer default 100,
  p_offset integer default 0)
returns jsonb language plpgsql security definer
set search_path = ''
as $list$
declare
  v_uid uuid := auth.uid();
  v_total integer;
  v_items jsonb;
begin
  if v_uid is null or not exists (
    select 1 from public.editorial_reviewers where user_id=v_uid
      and disabled_at is null) then
    raise exception 'Reviewer access required' using errcode='42501';
  end if;
  if p_state not in ('all','needs_primary_review','source_verified',
                     'ready_to_publish','published','rejected')
      or p_limit is null or p_limit not between 1 and 100
      or p_offset is null or p_offset not between 0 and 10000 then
    raise exception 'Invalid pagination or status filter';
  end if;
  select count(*)::integer into v_total
    from public.agenda_evidence_reviews r
    where p_state='all' or r.review_state=p_state;

  select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(t)), '[]'::jsonb)
  into v_items
  from (
    select
      r.discovery_queue_id as id,
      r.tenant, r.matter_id, r.official_api_url, r.official_page_url,
      r.original_discovery_url, r.reviewed_primary_source_url,
      r.suggested_topic, r.suspected_flock_reference,
      r.verified_vendor_relation, r.decision_outcome,
      r.review_state, r.reviewed_claim, r.reviewer_notes, r.action_date,
      r.reviewed_by, r.reviewed_at, r.updated_at,
      q.headline, q.publisher, q.snippet, q.discovered_at,
      q.status as queue_status
    from public.agenda_evidence_reviews r
    join public.discovery_queue q on q.id=r.discovery_queue_id
    where p_state='all' or r.review_state=p_state
    order by
      case r.review_state when 'needs_primary_review' then 0
        when 'source_verified' then 1 when 'ready_to_publish' then 2
        when 'rejected' then 3 else 4 end,
      r.created_at, r.tenant, r.matter_id
    limit p_limit offset p_offset
  ) t;
  return pg_catalog.jsonb_build_object('total',v_total, 'items',v_items);
end;
$list$;

-- The evidence API can only obtain tenant + numeric matter ID for a row that
-- a logged-in, expressly approved reviewer can already access.
create or replace function public.editorial_evidence_ref(p_review_id uuid)
returns jsonb language plpgsql security definer
set search_path = ''
as $evidence$
declare
  v_uid uuid := auth.uid();
  r record;
begin
  if v_uid is null or not exists (
    select 1 from public.editorial_reviewers where user_id=v_uid
      and disabled_at is null) then
    raise exception 'Reviewer access required' using errcode='42501';
  end if;
  select tenant,matter_id,official_api_url into r
    from public.agenda_evidence_reviews
    where discovery_queue_id=p_review_id;
  if not found then
    raise exception 'Review item not found' using errcode='P0002';
  end if;
  return pg_catalog.jsonb_build_object(
    'tenant',r.tenant,'matter_id',r.matter_id,'official_api_url',r.official_api_url);
end;
$evidence$;

-- All editorial changes are transactional and audit logged. An expected
-- revision protects simultaneous reviewers from overwriting one another.
-- "Approve" means evidence verified, never automatic public publication.
create or replace function public.editorial_decide(
  p_id uuid,
  p_action text,
  p_expected_updated_at timestamptz,
  p_topic text default null,
  p_vendor text default null,
  p_outcome text default null,
  p_primary_page text default null,
  p_claim text default null,
  p_action_date date default null,
  p_notes text default null
)
returns jsonb language plpgsql security definer
set search_path = ''
as $decide$
declare
  v_uid uuid := auth.uid();
  v_role text;
  r public.agenda_evidence_reviews%rowtype;
  q public.discovery_queue%rowtype;
  v_previous text;
  v_page text;
  v_label text;
  v_place text;
  v_state text;
  v_kind text;
  v_jurisdiction uuid;
  v_source uuid;
  v_action_kind text;
  v_existing uuid;
  v_event_id bigint;
begin
  if v_uid is null then
    raise exception 'Authentication required' using errcode='42501';
  end if;
  select role into v_role from public.editorial_reviewers
    where user_id=v_uid and disabled_at is null;
  if v_role is null then
    raise exception 'Reviewer access required' using errcode='42501';
  end if;
  if p_action is null or p_action not in ('save','approve','reject','reopen','publish') then
    raise exception 'Unknown editorial action';
  end if;
  if p_id is null or p_expected_updated_at is null then
    raise exception 'A review ID and revision timestamp are required';
  end if;

  select * into r from public.agenda_evidence_reviews
    where discovery_queue_id=p_id for update;
  if not found then raise exception 'Review item not found'; end if;
  if r.updated_at is distinct from p_expected_updated_at then
    raise exception 'This review changed since you opened it. Reload before making changes';
  end if;
  if r.review_state='published' then
    raise exception 'Published records are immutable in this dashboard';
  end if;
  select * into q from public.discovery_queue where id=p_id for update;
  if not found then raise exception 'Queue item not found'; end if;

  v_previous := r.review_state;
  if p_action='reopen' then
    if r.review_state <> 'rejected' then
      raise exception 'Only rejected findings can be reopened';
    end if;
    update public.agenda_evidence_reviews set
      review_state='needs_primary_review', reviewed_at=null,
      reviewed_by=null, updated_at=pg_catalog.clock_timestamp()
    where discovery_queue_id=p_id;
    update public.discovery_queue set status='in_review'
      where id=p_id;
  elsif p_action='publish' then
    if v_role <> 'publisher' then
      raise exception 'Publisher permission is required' using errcode='42501';
    end if;
    if r.review_state not in ('source_verified','ready_to_publish')
        or r.verified_vendor_relation <> 'explicit_flock'
        or r.decision_outcome not in ('proposed','approved','failed','heard','informational','other')
        or r.suggested_topic='unclassified'
        or r.reviewed_primary_source_url is null
        or r.reviewed_primary_source_url is distinct from r.official_page_url
        or r.reviewed_at is null or r.reviewed_by is null
        or r.action_date is null
        or nullif(pg_catalog.btrim(coalesce(r.reviewed_claim,'')),'') is null then
      raise exception 'Publishing requires approved Flock evidence, primary page, dated decision and reviewed claim';
    end if;
    -- Require a government-authorized tenant, not an arbitrary external URL.
    select jurisdiction_label into v_label
      from public.government_source_registry
      where source_kind='legistar' and verification_status='verified'
        and source_url='https://' || r.tenant || '.legistar.com/'
      limit 1;
    if v_label is null then
      raise exception 'The government Legistar tenant is not currently verified';
    end if;
    v_page := 'https://' || r.tenant || '.legistar.com/LegislationDetail.aspx';
    if pg_catalog.left(r.reviewed_primary_source_url,pg_catalog.length(v_page)) <> v_page
       or r.reviewed_primary_source_url !~* '[?&]ID=[0-9]+([&#]|$)'
       or r.reviewed_primary_source_url !~* '[?&]GUID=[A-Fa-f0-9-]{36}([&#]|$)'
       or pg_catalog.length(r.reviewed_primary_source_url)>1200 then
      raise exception 'Source must be the identity-matched official Legistar detail page with GUID and ID';
    end if;
    v_state := pg_catalog.upper(pg_catalog.btrim(pg_catalog.split_part(v_label,',',2)));
    v_place := pg_catalog.btrim(pg_catalog.split_part(v_label,',',1));
    if v_state !~ '^[A-Z]{2}$' or v_place='' then
      raise exception 'Government jurisdiction is missing a valid state and name';
    end if;
    v_kind := case when v_place ilike '% County' then 'county' else 'city' end;
    -- Refuse to overwrite a rejected government primary source.
    if exists(select 1 from public.sources where url=r.official_page_url
              and status='rejected') then
      raise exception 'The government source has been rejected';
    end if;
    insert into public.jurisdictions(state_code,name,kind)
      values(v_state,v_place,v_kind)
      on conflict(state_code,name,kind) do nothing;
    select id into v_jurisdiction from public.jurisdictions
      where state_code=v_state and name=v_place and kind=v_kind;
    insert into public.sources(url,title,publisher,source_type,status)
      values(r.official_page_url,pg_catalog.left(q.headline,300),v_label,
             'official_government_legislative_record','verified')
      on conflict(url) do nothing;
    select id into v_source from public.sources
      where url=r.official_page_url and status='verified';
    if v_source is null then
      raise exception 'Could not verify the source or source was rejected';
    end if;
    -- One published government matter per exact public source; changes to
    -- an already published matter require separate editorial correction flow.
    select id into v_existing from public.actions
      where source_id=v_source and review_status='published' limit 1;
    if v_existing is not null then
      raise exception 'A published decision already exists for this government source';
    end if;
    v_action_kind := case
      when r.decision_outcome='approved' and r.suggested_topic='contract_or_procurement'
        then 'contract_approval'
      when r.decision_outcome='approved' and r.suggested_topic='policy_or_oversight'
        then 'policy_change'
      when r.decision_outcome='heard' then 'hearing'
      else 'other' end;
    insert into public.actions (
        jurisdiction_id,action_type,action_date,factual_description,
        recorded_position,source_id,review_status)
      values(v_jurisdiction,v_action_kind,r.action_date,r.reviewed_claim,
             'not_applicable',v_source,'published');
    update public.agenda_evidence_reviews
      set review_state='published', updated_at=pg_catalog.clock_timestamp()
      where discovery_queue_id=p_id;
    update public.discovery_queue set status='accepted',
      reviewer_notes=pg_catalog.left(coalesce(r.reviewer_notes,'') ||
        ' | Published after primary-source editorial review',5000)
      where id=p_id;
  else
    -- For draft/save/reject/approve, apply only the current vetted fields.
    if p_action='approve' and r.review_state='rejected' then
      raise exception 'Reopen a rejected finding before approving it';
    end if;
    if p_action='reject' and nullif(pg_catalog.btrim(coalesce(p_notes,'')),'') is null then
      raise exception 'A rejection explanation is required';
    end if;
    if p_topic is null or p_topic not in
       ('unclassified','contract_or_procurement','presentation','policy_or_oversight')
       or p_vendor is null or p_vendor not in
       ('not_assessed','explicit_flock','different_vendor','general_alpr','indeterminate')
       or p_outcome is null or p_outcome not in
       ('not_assessed','proposed','approved','failed','heard','informational','other')
       or pg_catalog.length(coalesce(p_claim,''))>1600
       or pg_catalog.length(coalesce(p_notes,''))>5000
       or pg_catalog.length(coalesce(p_primary_page,''))>1200 then
      raise exception 'Invalid editorial classification or text length';
    end if;
    v_page := nullif(pg_catalog.btrim(coalesce(p_primary_page,'')),'');
    if v_page is not null and (
       pg_catalog.left(v_page, pg_catalog.length('https://' || r.tenant || '.legistar.com/LegislationDetail.aspx')) <>
         'https://' || r.tenant || '.legistar.com/LegislationDetail.aspx'
       or v_page !~* '[?&]ID=[0-9]+([&#]|$)'
       or v_page !~* '[?&]GUID=[A-Fa-f0-9-]{36}([&#]|$)'
       ) then
      raise exception 'Use the actual official Legistar detail page for this tenant with GUID and ID';
    end if;
    if p_action='approve' and (v_page is null or p_topic='unclassified'
       or p_vendor='not_assessed' or p_outcome='not_assessed'
       or nullif(pg_catalog.btrim(coalesce(p_claim,'')),'') is null) then
      raise exception 'Verify the source page and complete topic, vendor, outcome and claim before approving';
    end if;
    update public.agenda_evidence_reviews
      set suggested_topic=p_topic,
          verified_vendor_relation=p_vendor,
          decision_outcome=p_outcome,
          official_page_url=v_page,
          reviewed_primary_source_url=
            case when p_action='approve' then v_page else null end,
          reviewed_claim=nullif(pg_catalog.btrim(coalesce(p_claim,'')),''),
          reviewer_notes=nullif(pg_catalog.btrim(coalesce(p_notes,'')),''),
          action_date=p_action_date,
          reviewed_by=case when p_action='approve' then v_uid::text else null end,
          reviewed_at=case when p_action='approve' then now() else null end,
          review_state=case when p_action='approve' then 'source_verified'
             when p_action='reject' then 'rejected' else 'needs_primary_review' end,
          updated_at=pg_catalog.clock_timestamp()
      where discovery_queue_id=p_id;
    update public.discovery_queue set status=
      case when p_action='reject' then 'rejected' else 'in_review' end
      where id=p_id;
  end if;
  insert into public.editorial_review_events(
    review_id,actor_id,event_type,old_state,new_state,details)
  select p_id,v_uid,p_action,v_previous,review_state,
    pg_catalog.jsonb_build_object(
      'topic',suggested_topic, 'vendor',verified_vendor_relation,
      'outcome',decision_outcome, 'page',official_page_url,
      'claim',reviewed_claim, 'action_date',action_date)
    from public.agenda_evidence_reviews where discovery_queue_id=p_id
    returning id into v_event_id;
  return pg_catalog.jsonb_build_object(
    'ok',true,'event_id',v_event_id,
    'review_state',(select review_state from public.agenda_evidence_reviews
                    where discovery_queue_id=p_id));
end;
$decide$;

-- Explicit grants. All other roles (including anon) have no executable access.
revoke all on function public.editorial_session() from public, anon;
revoke all on function public.editorial_list(text,integer,integer) from public, anon;
revoke all on function public.editorial_evidence_ref(uuid) from public, anon;
revoke all on function public.editorial_decide(
  uuid,text,timestamptz,text,text,text,text,text,date,text) from public, anon;
grant execute on function public.editorial_session() to authenticated;
grant execute on function public.editorial_list(text,integer,integer) to authenticated;
grant execute on function public.editorial_evidence_ref(uuid) to authenticated;
grant execute on function public.editorial_decide(
  uuid,text,timestamptz,text,text,text,text,text,date,text) to authenticated;
