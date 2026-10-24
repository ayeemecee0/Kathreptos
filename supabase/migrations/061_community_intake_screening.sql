-- Repair per-user intake limiter using an isolated private counter.
create table if not exists public.flock_submission_rate_buckets (
 user_id uuid primary key references auth.users(id) on delete cascade,
 window_started_at timestamptz not null default now(),
 submitted_count integer not null default 0 check(submitted_count between 0 and 3)
);
alter table public.flock_submission_rate_buckets enable row level security;
revoke all on public.flock_submission_rate_buckets from public,anon,authenticated;
create or replace function katoptron_internal.throttle_community_report()
returns trigger language plpgsql security definer set search_path=''
as $$
declare n integer;
begin
 if (select auth.uid()) is null or new.submitter_id is distinct from (select auth.uid()) then
   raise exception 'Authentication required' using errcode='42501';
 end if;
 insert into public.flock_submission_rate_buckets(user_id,window_started_at,submitted_count)
 values(new.submitter_id,now(),1)
 on conflict(user_id) do update set
   window_started_at=case when public.flock_submission_rate_buckets.window_started_at < now()-interval '24 hours' then now() else public.flock_submission_rate_buckets.window_started_at end,
   submitted_count=case when public.flock_submission_rate_buckets.window_started_at < now()-interval '24 hours' then 1 else public.flock_submission_rate_buckets.submitted_count+1 end
 returning submitted_count into n;
 if n>3 then raise exception 'Maximum three submissions per 24 hours'; end if;
 return new;
end $$;
revoke all on function katoptron_internal.throttle_community_report() from public,anon,authenticated;
create table if not exists public.flock_community_screening (
 submission_id uuid primary key references public.flock_community_submissions(submission_id) on delete cascade,
 screening_state text not null check(screening_state in ('review_needed','possible_duplicate','near_existing_verified')),
 related_submission_count integer not null,
 matching_verified_count integer not null,
 screened_at timestamptz not null default now()
);
alter table public.flock_community_screening enable row level security;
revoke all on public.flock_community_screening from public,anon,authenticated;
create or replace function katoptron_internal.screen_community_report()
returns trigger language plpgsql security definer set search_path=''
as $$
declare prior_n integer; known_n integer;
begin
 select count(*) into prior_n from public.flock_community_submissions x
 where x.submission_id<>new.submission_id and x.created_at<=new.created_at
 and abs(x.latitude-new.latitude)<=0.0003
 and abs(x.longitude-new.longitude)*cos(radians(new.latitude))<=0.0003;
 select count(*) into known_n from public.flock_camera_locations x
 where x.verification_status='verified'
 and abs(x.latitude-new.latitude)<=0.0003
 and abs(x.longitude-new.longitude)*cos(radians(new.latitude))<=0.0003;
 insert into public.flock_community_screening(submission_id,screening_state,related_submission_count,matching_verified_count)
 values(new.submission_id,case when known_n>0 then 'near_existing_verified'
 when prior_n>0 then 'possible_duplicate' else 'review_needed' end,
 least(prior_n,99999),least(known_n,99999));
 return new;
end $$;
revoke all on function katoptron_internal.screen_community_report() from public,anon,authenticated;
create trigger community_screen_insert after insert on public.flock_community_submissions
for each row execute function katoptron_internal.screen_community_report();