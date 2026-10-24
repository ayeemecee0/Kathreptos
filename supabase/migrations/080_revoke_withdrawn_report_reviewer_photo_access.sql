-- 080: A withdrawn contributor report must revoke reviewer visibility even if
-- the user's Storage API delete could not complete due to a network outage.
-- Do NOT hide the user's own Storage SELECT permission: the reporter needs it
-- to list the orphaned object and retry deletion under migration 067.
-- Private bucket and physical object lifecycle remain independently enforced.

create or replace function katoptron_internal.active_report_photo(p_object_path text)
returns boolean language sql stable security definer set search_path=''
as $$
 select exists(
   select 1 from public.flock_community_submissions s
   where s.submitter_id::text=(storage.foldername(p_object_path))[1]
     and s.submission_id::text=(storage.foldername(p_object_path))[2]
     and s.report_status<>'withdrawn'
 );
$$;
revoke all on function katoptron_internal.active_report_photo(text)
 from public,anon,authenticated;
grant execute on function katoptron_internal.active_report_photo(text)
 to authenticated;

-- The editorial gate is still independently checked; this extra predicate
-- prevents direct object downloads (not just signed-URL listing) for withdrawn
-- cases, even if their physical blobs remain until the reporter retries delete.
alter policy katoptron_reviewer_read_report_evidence on storage.objects
 using (
   bucket_id='katoptron-community-evidence'
   and coalesce(((select public.editorial_session())->>'authorized')::boolean,false)
   and katoptron_internal.active_report_photo(name)
 );

-- A reviewer cannot mint NEW signed URLs for a withdrawn report even if
-- the file still exists; preserve owner-only caller authorization.
create or replace function public.community_report_attachment_paths(p_report uuid)
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
   and s.report_status<>'withdrawn'
   and o.name like s.submitter_id::text||'/'||s.submission_id::text||'/%'
 order by o.name limit 5;
end $$;
revoke all on function public.community_report_attachment_paths(uuid)
 from public,anon,authenticated;
grant execute on function public.community_report_attachment_paths(uuid)
 to authenticated;

comment on function katoptron_internal.active_report_photo(text) is
'Internal non-public Storage RLS helper: withdrawn report blobs are hidden from reviewers pending owner deletion.';
