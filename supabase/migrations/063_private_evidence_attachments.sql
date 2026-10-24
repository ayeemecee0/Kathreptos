-- 063: Private evidence attachments, scoped to a signed-in reporter's existing case.
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('katoptron-community-evidence','katoptron-community-evidence',false,3145728,
array['image/jpeg','image/png','image/webp'])
on conflict(id) do nothing;
create policy katoptron_reporter_upload_own_evidence
on storage.objects for insert to authenticated
with check (
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists(
 select 1 from public.flock_community_submissions s
 where s.submitter_id=(select auth.uid()) and s.submission_id::text=(storage.foldername(name))[2]
 and s.report_status='pending')
);
create policy katoptron_reporter_read_own_evidence
on storage.objects for select to authenticated
using (
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
);
-- Reviewers can inspect originals. Everyone else remains limited to their own submissions.
create policy katoptron_reviewer_read_report_evidence
on storage.objects for select to authenticated
using (
 bucket_id='katoptron-community-evidence'
 and exists(select 1 from public.editorial_reviewers r
 where r.user_id=(select auth.uid()) and r.disabled_at is null)
);
