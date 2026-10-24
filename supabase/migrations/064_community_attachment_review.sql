-- 064: Private attachment discovery for authorized reviewers only.
-- Read-only metadata; actual downloads require Storage RLS and short-lived signed URLs.
create function public.community_report_attachment_paths(p_report uuid)
returns table(object_path text)
language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null or not exists(
  select 1 from public.editorial_reviewers r
  where r.user_id=auth.uid() and r.disabled_at is null
 ) then raise exception 'Reviewer access required' using errcode='42501'; end if;
 return query select o.name from storage.objects o
 join public.flock_community_submissions s
 on s.submission_id=p_report
 where o.bucket_id='katoptron-community-evidence'
 and o.name like s.submitter_id::text||'/'||s.submission_id::text||'/%'
 order by o.name limit 5;
end $$;
revoke all on function public.community_report_attachment_paths(uuid) from public,anon,authenticated;
grant execute on function public.community_report_attachment_paths(uuid) to authenticated;
-- Make upload paths deterministic, bounded, and account/report-scoped.
alter policy katoptron_reporter_upload_own_evidence on storage.objects
with check(
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and storage.filename(name) in ('evidence.jpg','evidence.png','evidence.webp')
 and exists(select 1 from public.flock_community_submissions s
 where s.submitter_id=(select auth.uid())
 and s.submission_id::text=(storage.foldername(name))[2]
 and s.report_status='pending')
);