-- 065: Reviewer decisions are audited. Incorporation stages a candidate only.
create table public.flock_community_review_history (
 id bigint generated always as identity primary key,
 submission_id uuid not null references public.flock_community_submissions(submission_id) on delete cascade,
 reviewer_id uuid not null references auth.users(id),
 previous_status text not null,
 new_status text not null,
 note text not null,
 changed_at timestamptz not null default now()
);
alter table public.flock_community_review_history enable row level security;
revoke all on public.flock_community_review_history from public,anon,authenticated;
create or replace function public.set_community_review_status(p_id uuid,p_status text,p_note text default '')
returns void language plpgsql security definer set search_path='' as $$
declare s public.flock_community_submissions%rowtype;
caseid text;
sourcehash text;
begin
 if (select auth.uid()) is null or not exists(
 select 1 from public.editorial_reviewers r where r.user_id=auth.uid() and r.disabled_at is null
 ) then raise exception 'Reviewer access required' using errcode='42501'; end if;
 if p_status not in ('needs_evidence','rejected','incorporated') then
 raise exception 'Invalid review outcome'; end if;
 if length(btrim(coalesce(p_note,''))) < 15 then
 raise exception 'Reviewer explanation must be at least 15 characters'; end if;
 select * into s from public.flock_community_submissions
 where submission_id=p_id and report_status in ('pending','needs_evidence')
 for update;
 if not found then raise exception 'Report not found or already reviewed'; end if;
 if p_status='incorporated' then
  if s.original_source_url is null then
   raise exception 'An original source URL is required to stage a research candidate'; end if;
  caseid:='tier_'||md5(s.submission_id::text);
  sourcehash:=encode(sha256(convert_to(s.description||'|'||s.original_source_url||'|'||s.latitude::text||'|'||s.longitude::text,'UTF8')),'hex');
  insert into public.flock_point_evidence_cases
    (case_key,label,jurisdiction_label,latitude,longitude,evidence_summary,source_url)
  values(caseid,'Community-reported possible Flock device','Community report; jurisdiction unverified',
    s.latitude,s.longitude,
    left('Community-contributed report, awaiting independent validation. '||s.description,1500),
    s.original_source_url)
  on conflict(case_key) do nothing;
  insert into public.flock_point_evidence_attestations
    (evidence_key,case_key,source_kind,source_family,source_url,latitude,longitude,evidence_sha256,source_excerpt)
  values('proof_'||md5(s.submission_id::text),caseid,'community_report',
    'katoptron.community',s.original_source_url,s.latitude,s.longitude,sourcehash,left(s.description,900))
  on conflict(evidence_key) do nothing;
 end if;
 update public.flock_community_submissions set report_status=p_status where submission_id=p_id;
 insert into public.flock_community_review_history(submission_id,reviewer_id,previous_status,new_status,note)
 values(p_id,auth.uid(),s.report_status,p_status,btrim(p_note));
end $$;
revoke all on function public.set_community_review_status(uuid,text,text) from public,anon,authenticated;
grant execute on function public.set_community_review_status(uuid,text,text) to authenticated;
revoke all on function public.set_community_review_status(uuid,text) from public,anon,authenticated;
-- Old two-argument overload is intentionally disabled.
