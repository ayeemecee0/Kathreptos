#!/usr/bin/env bash
# CI-only recovery rehearsal. Disposable local PostgreSQL, synthetic fixtures.
# NEVER point this script at production or an owner's private backup.
set -euo pipefail
source_db=katoptron_test
restore_db=katoptron_recovery_test
host=127.0.0.1
user=postgres
case_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
other_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
dir=$(mktemp -d)
cleanup() {
  dropdb --if-exists -h "$host" -U "$user" "$restore_db" >/dev/null 2>&1 || true
  rm -rf "$dir"
}
trap cleanup EXIT
test -n "$PGPASSWORD" || { echo 'CI-only PostgreSQL password required'; exit 1; }
test "$GITHUB_ACTIONS" = true || { echo 'CI-only rehearsal refused outside GitHub Actions'; exit 1; }
test "$GITHUB_REPOSITORY" = "ayeemecee0/Katoptron" || {
  echo 'Recovery rehearsal repository must match Katoptron'; exit 1;
}
test "$host" = '127.0.0.1'
test "$source_db" = 'katoptron_test'
test "$restore_db" = 'katoptron_recovery_test'
psql -X -v ON_ERROR_STOP=1 -h "$host" -U "$user" -d "$source_db" >/dev/null <<SQL
insert into auth.users(id) values ('$case_id'),('$other_id')
on conflict (id) do nothing;
begin;
select set_config('request.jwt.claim.sub','$case_id',true);
set local role authenticated;
insert into public.flock_community_submissions
 (latitude,longitude,description,consent_to_review,publication_consent)
values (38.55,-121.46,
 'FICTIONAL ephemeral CI restore fixture. Not a real Flock Safety camera; do not publish.',true,false);
commit;
SQL
# Full CI DB dump contains only synthetic Auth identities, not managed
# Supabase Auth accounts nor any production private Storage binary objects.
pg_dump -h "$host" -U "$user" -d "$source_db" --format=custom \
  --no-owner --file="$dir/application-fixture.dump"
test -s "$dir/application-fixture.dump"
pg_restore --list "$dir/application-fixture.dump" >"$dir/restore-manifest.txt"
grep -q 'flock_community_submissions' "$dir/restore-manifest.txt" || {
  echo 'Restore source missing community reporting table'; exit 1;
}
grep -q 'TABLE DATA.*flock_community_submissions' "$dir/restore-manifest.txt" || {
  echo 'Restore source missing community report data'; exit 1;
}
createdb -h "$host" -U "$user" -T template0 "$restore_db"
pg_restore -h "$host" -U "$user" -d "$restore_db" \
  --no-owner --exit-on-error "$dir/application-fixture.dump" >/dev/null
psql -X -v ON_ERROR_STOP=1 -h "$host" -U "$user" -d "$restore_db" >/dev/null <<SQL
do \$verify\$
begin
 if (select count(*) from public.flock_community_submissions
     where submitter_id='$case_id'::uuid
       and publication_consent=false
       and report_status='pending')<>1 then
   raise exception 'Private report row or explicit non-public consent not recovered';
 end if;
 if (select count(*) from auth.users where id in ('$case_id'::uuid,'$other_id'::uuid))<>2 then
   raise exception 'Foreign-key synthetic identity integrity not recovered';
 end if;
 if (select count(*) from public.government_source_registry)=0 then
   raise exception 'Official government source baseline missing from restore';
 end if;
 if not (select relrowsecurity from pg_class
    where oid='public.flock_community_submissions'::regclass) then
   raise exception 'Recovered private report RLS disabled';
 end if;
 if has_table_privilege('anon','public.flock_community_submissions','SELECT')
   or has_table_privilege('anon','public.flock_community_submissions','INSERT')
   or has_table_privilege('authenticated','public.editorial_reviewers','SELECT') then
   raise exception 'Recovered private access grants are not safe';
 end if;
end \$verify\$;
SQL
# Verify restored row isolation using real authenticated PostgreSQL role.
owner_count=$(psql -X -A -t -v ON_ERROR_STOP=1 -h "$host" -U "$user" -d "$restore_db" <<SQL
begin;
select set_config('request.jwt.claim.sub','$case_id',true) is not null;
set local role authenticated;
select count(*) from public.flock_community_submissions;
rollback;
SQL
)
test "$(printf '%s\n' "$owner_count" | grep -E '^[0-9]+$' | tail -1)" = 1 || {
  echo 'Recovered RLS owner cannot see private fixture'; exit 1;
}
other_count=$(psql -X -A -t -v ON_ERROR_STOP=1 -h "$host" -U "$user" -d "$restore_db" <<SQL
begin;
select set_config('request.jwt.claim.sub','$other_id',true) is not null;
set local role authenticated;
select count(*) from public.flock_community_submissions;
rollback;
SQL
)
test "$(printf '%s\n' "$other_count" | grep -E '^[0-9]+$' | tail -1)" = 0 || {
  echo 'Recovered RLS exposes private reports to other contributors'; exit 1;
}
exposed=$(psql -X -A -t -v ON_ERROR_STOP=1 -h "$host" -U "$user" -d "$restore_db" \
  -c "select count(*) from public.flock_camera_locations where latitude=38.55 and longitude=-121.46;")
test "$exposed" = 0 || {
  echo 'Recovered unpublished fixture escaped into verified map'; exit 1;
}
echo 'LOCAL RECOVERY REHEARSAL PASS: disposable DB dump restored; synthetic private rows, government records, FK and RLS isolation verified.'
echo 'This does NOT verify an owner backup, real Auth identities, Storage photos, or production disaster recovery.'
