-- 073: Individual officials' positions require explicit original government evidence.
-- Government-wide measures, inferred affiliation and agenda listings do not qualify.
create table public.flock_individual_public_positions (
 position_key text primary key check(position_key ~ '^[a-z0-9_-]{12,100}$'),
 person_name text not null check(length(person_name) between 5 and 130),
 office_title text not null check(length(office_title) between 4 and 140),
 jurisdiction_label text not null check(length(jurisdiction_label) between 4 and 130),
 state_code text not null check(state_code ~ '^[A-Z]{2}$'),
 record_kind text not null check(record_kind in ('individual_roll_call_vote','direct_public_statement')),
 recorded_position text not null check(recorded_position in ('yes','no','abstain','recused','other_explicit_statement')),
 action_date date not null check(action_date>=date '2000-01-01' and action_date<=current_date),
 document_reference text not null check(length(document_reference) between 6 and 160),
 evidence_description text not null check(length(evidence_description) between 40 and 950),
 original_government_url text not null check(
   original_government_url ~ '^https://[A-Za-z0-9.-]+/' and length(original_government_url)<=1600),
 source_kind text not null check(source_kind in ('official_government_minutes','original_roll_call','official_recorded_statement')),
 record_status text not null default 'candidate' check(record_status in ('candidate','verified','withdrawn')),
 verified_at timestamptz,
 last_checked_at timestamptz,
 check(record_status<>'verified' or (verified_at is not null and last_checked_at is not null)),
 check((record_kind='individual_roll_call_vote'
  and source_kind in ('original_roll_call','official_government_minutes')
  and recorded_position in ('yes','no','abstain','recused'))
  or (record_kind='direct_public_statement' and
      source_kind='official_recorded_statement' and
      recorded_position='other_explicit_statement'))
);
alter table public.flock_individual_public_positions enable row level security;
revoke all on public.flock_individual_public_positions from public,anon,authenticated,service_role;
grant select(position_key,person_name,office_title,jurisdiction_label,state_code,
record_kind,recorded_position,action_date,document_reference,evidence_description,
original_government_url,source_kind,verified_at,last_checked_at)
on public.flock_individual_public_positions to anon,authenticated;
create policy published_proven_individual_positions_only
on public.flock_individual_public_positions for select to anon,authenticated
using(record_status='verified' and verified_at is not null and last_checked_at is not null);
comment on table public.flock_individual_public_positions is
'Only explicit named original-government roll-call votes or directly recorded official statements; no agency-action-to-politician inference and no automatic workflow publication.';
