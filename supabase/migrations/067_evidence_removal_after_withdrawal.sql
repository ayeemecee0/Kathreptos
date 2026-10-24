-- 067: Withdrawn reporters can erase their own evidence attachments.
create policy katoptron_reporter_delete_withdrawn_photos
on storage.objects for delete to authenticated
using(
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists (
  select 1 from public.flock_community_submissions s
  where s.submitter_id=(select auth.uid())
  and s.submission_id::text=(storage.foldername(name))[2]
  and s.report_status='withdrawn'
 )
);
