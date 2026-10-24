-- 062: Reviewer-only private triage RPCs. Status edits do not publish evidence.
create function public.list_community_review_queue(p_limit int default 50)
returns table(submission_id uuid,latitude double precision,longitude double precision,
description text,original_source_url text,observed_on date,report_status text,
created_at timestamptz,screening_state text,related_submission_count integer,matching_verified_count integer)
language plpgsql security definer set search_path='' as $$
begin
 if (select auth.uid()) is null or not exists (
 select 1 from public.editorial_reviewers r where r.user_id=auth.uid() and r.disabled_at is null
 ) then raise exception 'Reviewer access required' using errcode='42501'; end if;
 return query
 select s.submission_id,s.latitude,s.longitude,s.description,s.original_source_url,s.observed_on,s.report_status,
 s.created_at,t.screening_state,t.related_submission_count,t.matching_verified_count
 from public.flock_community_submissions s
 left join public.flock_community_screening t on t.submission_id=s.submission_id
 where s.report_status in ('pending','needs_evidence')
 order by s.created_at asc limit least(greatest(coalesce(p_limit,50),1),100);
end $$;
revoke all on function public.list_community_review_queue(int) from public,anon,authenticated;
grant execute on function public.list_community_review_queue(int) to authenticated;
create function public.set_community_review_status(p_id uuid,p_status text)
returns void language plpgsql security definer set search_path='' as $$
begin
 if (select auth.uid()) is null or not exists (
 select 1 from public.editorial_reviewers r where r.user_id=auth.uid() and r.disabled_at is null
 ) then raise exception 'Reviewer access required' using errcode='42501'; end if;
 if p_status not in ('needs_evidence','rejected','incorporated') then
 raise exception 'Invalid review outcome'; end if;
 update public.flock_community_submissions
 set report_status=p_status
 where submission_id=p_id and report_status in ('pending','needs_evidence');
 if not found then raise exception 'Report not found or already reviewed'; end if;
end $$;
revoke all on function public.set_community_review_status(uuid,text) from public,anon,authenticated;
grant execute on function public.set_community_review_status(uuid,text) to authenticated;
