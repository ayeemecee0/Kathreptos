-- 075: Resolve two independently reported missing FK indexes in private review history.
-- Supports owner deletion and evidence withdrawal without table-wide scans.
create index if not exists flock_community_review_history_reviewer_fk_idx
on public.flock_community_review_history(reviewer_id,changed_at desc);
create index if not exists flock_community_review_history_submission_fk_idx
on public.flock_community_review_history(submission_id,changed_at desc);
