-- 079: Let the original submitter add a missing HTTPS evidence link once.
-- No editing/replacing existing links, no status changes, no private owner-ID grant.
-- The source is a lead; it cannot publish a point without independent evidence.
grant update(original_source_url) on public.flock_community_submissions to authenticated;
create policy contributor_adds_missing_original_source_once
on public.flock_community_submissions
for update to authenticated
using (
 submitter_id=(select auth.uid())
 and report_status in ('pending','needs_evidence')
 and original_source_url is null
)
with check (
 submitter_id=(select auth.uid())
 and report_status in ('pending','needs_evidence')
 and original_source_url is not null
);
