-- 060: Signed-in community reports are private evidence leads, never public pins.
-- Does not grant insert/update access to verified cases, attestations or camera locations.
create table public.flock_community_submissions (
  submission_id uuid primary key default gen_random_uuid(),
  submitter_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  latitude double precision not null check(latitude between 17 and 72),
  longitude double precision not null check(longitude between -180 and -64),
  description text not null check(length(btrim(description)) between 40 and 1500),
  original_source_url text check(original_source_url is null or
    (original_source_url ~ '^https://[A-Za-z0-9.-]+(/|$)' and length(original_source_url) <= 1600)),
  observed_on date check(observed_on is null or (observed_on <= current_date and observed_on >= date '2000-01-01')),
  consent_to_review boolean not null check(consent_to_review = true),
  report_status text not null default 'pending' check(report_status in ('pending','needs_evidence','rejected','withdrawn','incorporated')),
  created_at timestamptz not null default now()
);
create index flock_community_submissions_user_recent_idx
  on public.flock_community_submissions(submitter_id,created_at desc);
alter table public.flock_community_submissions enable row level security;
revoke all on public.flock_community_submissions from public,anon,authenticated,service_role;
grant usage on schema public to authenticated;
grant select(submission_id,latitude,longitude,description,original_source_url,observed_on,report_status,created_at)
  on public.flock_community_submissions to authenticated;
grant insert(latitude,longitude,description,original_source_url,observed_on,consent_to_review)
  on public.flock_community_submissions to authenticated;
create policy submitter_can_read_own_report on public.flock_community_submissions
  for select to authenticated using (submitter_id = (select auth.uid()));
create policy signed_in_user_may_submit_unreviewed_report on public.flock_community_submissions
  for insert to authenticated with check (
    submitter_id = (select auth.uid()) and report_status = 'pending'
  );
-- Serialize per-account writes: prevents simultaneous requests bypassing daily caps.
create function katoptron_internal.throttle_community_report()
returns trigger language plpgsql security invoker set search_path=''
as $body$
begin
  if auth.uid() is null or new.submitter_id is distinct from auth.uid() then
    raise exception 'Authenticated owner required' using errcode='42501';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(new.submitter_id::text,0));
  if (select count(*) from public.flock_community_submissions
      where submitter_id=new.submitter_id and created_at >= now()-interval '24 hours') >= 3 then
    raise exception 'Maximum 3 reports per 24 hours' using errcode='P0001';
  end if;
  return new;
end;
$body$;
revoke all on function katoptron_internal.throttle_community_report() from public,anon,authenticated;
create trigger throttle_community_reports before insert on public.flock_community_submissions
 for each row execute function katoptron_internal.throttle_community_report();
-- No anonymous insert/read. No public view or publication trigger. A submission is not evidence approval.
