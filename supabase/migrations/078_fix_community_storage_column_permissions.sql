-- 078: Repair real Supabase Storage RLS without disclosing private owner IDs.
-- Community row SELECT already filters submitter_id = auth.uid(), so do not
-- reference submitter_id directly inside invoker Storage policies: authenticated
-- role intentionally has no SELECT permission for that private column.
alter policy katoptron_reporter_upload_own_evidence on storage.objects
with check(
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and storage.filename(name) in ('evidence.jpg','evidence.png','evidence.webp')
 and exists(
   select 1 from public.flock_community_submissions s
   where s.submission_id::text=(storage.foldername(name))[2]
     and s.report_status in ('pending','needs_evidence')
 )
);
-- After withdrawal, allow the same reporter to erase their own private
-- object through the Storage API, without granting owner-column visibility.
alter policy katoptron_reporter_delete_withdrawn_photos on storage.objects
using(
 bucket_id='katoptron-community-evidence'
 and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists(
   select 1 from public.flock_community_submissions s
   where s.submission_id::text=(storage.foldername(name))[2]
     and s.report_status='withdrawn'
 )
);
-- editorial_reviewers is intentionally unreadable by ordinary authenticated
-- users. Reuse the existing, authenticated, SECURITY DEFINER editorial_session()
-- endpoint, which returns only the caller's own authorized reviewer flag.
alter policy katoptron_reviewer_read_report_evidence on storage.objects
using (
 bucket_id='katoptron-community-evidence'
 and coalesce(((select public.editorial_session())->>'authorized')::boolean,false)
);
