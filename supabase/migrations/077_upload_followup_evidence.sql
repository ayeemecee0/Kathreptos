-- 077: A request for more evidence must not block the contributor from
-- attaching a private, original photo to the existing report.
-- Existing filenames remain deterministic; replacements/upserts stay prohibited.
alter policy katoptron_reporter_upload_own_evidence on storage.objects
with check (
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and storage.filename(name) in ('evidence.jpg','evidence.png','evidence.webp')
 and exists(
   select 1 from public.flock_community_submissions s
   where s.submitter_id=(select auth.uid())
    and s.submission_id::text=(storage.foldername(name))[2]
    and s.report_status in ('pending','needs_evidence')
 )
);
