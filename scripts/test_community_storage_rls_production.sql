-- Production-only Supabase Storage metadata RLS QA.
-- Run as one transaction. Never change the stored object list permanently:
-- object metadata is inserted and deleted before ROLLBACK, no blobs are written.
begin;
select set_config('katoptron.storage_owner',gen_random_uuid()::text,true);
select set_config('katoptron.storage_other',gen_random_uuid()::text,true);
select set_config('katoptron.storage_editor',gen_random_uuid()::text,true);
insert into auth.users(id) values
 (current_setting('katoptron.storage_owner')::uuid),
 (current_setting('katoptron.storage_other')::uuid),
 (current_setting('katoptron.storage_editor')::uuid);
insert into public.editorial_reviewers(user_id,role,granted_by)
values(current_setting('katoptron.storage_editor')::uuid,'publisher','rollback-only-storage-qa');
select set_config('request.jwt.claim.sub',current_setting('katoptron.storage_owner'),true);
set local role authenticated;
with s as (
 insert into public.flock_community_submissions(latitude,longitude,description,consent_to_review)
 values(38.61,-121.42,'Synthetic temporary storage authorization test. No real Flock Safety camera is being reported.',true)
 returning submission_id
) select set_config('katoptron.storage_case',submission_id::text,true) from s;
insert into storage.objects(bucket_id,name,owner,owner_id)
values('katoptron-community-evidence',
 current_setting('katoptron.storage_owner')||'/'||current_setting('katoptron.storage_case')||'/evidence.webp',
 current_setting('katoptron.storage_owner')::uuid,current_setting('katoptron.storage_owner'));
do $qa$
begin
 if (select count(*) from storage.objects
 where bucket_id='katoptron-community-evidence'
 and name like current_setting('katoptron.storage_owner')||'/%')<>1 then
 raise exception 'Owner cannot read own private Storage metadata';end if;
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.storage_other'),true);
do $qa$
begin
 if exists(select 1 from storage.objects
  where name like current_setting('katoptron.storage_owner')||'/%')
 then raise exception 'Second user read first user private Storage metadata';end if;
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.storage_editor'),true);
do $qa$
begin
 if (select count(*) from storage.objects
   where name like current_setting('katoptron.storage_owner')||'/%')<>1 then
 raise exception 'Reviewer cannot access authorized private photo';end if;
 perform public.set_community_review_status(
 current_setting('katoptron.storage_case')::uuid,'needs_evidence',
 'Synthetic reviewer requests an additional source photograph in the rollback-only test.');
end $qa$;
select set_config('request.jwt.claim.sub',current_setting('katoptron.storage_owner'),true);
insert into storage.objects(bucket_id,name,owner,owner_id)
values('katoptron-community-evidence',
 current_setting('katoptron.storage_owner')||'/'||current_setting('katoptron.storage_case')||'/evidence.jpg',
 current_setting('katoptron.storage_owner')::uuid,current_setting('katoptron.storage_owner'));
do $qa$
begin
 if (select count(*) from storage.objects
 where name like current_setting('katoptron.storage_owner')||'/%')<>2
 then raise exception 'Contributor cannot add requested followup photo metadata';end if;
 if not public.withdraw_own_community_report(current_setting('katoptron.storage_case')::uuid)
 then raise exception 'Owner could not withdraw report';end if;
end $qa$;
-- Supabase intentionally refuses direct SQL DELETE on storage.objects.
-- Confirm the owner's rows remain readable and the Storage API DELETE policy
-- exists; browser tests exercise .remove() against the Storage API contract.
do $qa$
begin
 if (select count(*) from storage.objects
   where name like current_setting('katoptron.storage_owner')||'/%')<>2 then
  raise exception 'Private evidence unreadable after withdrawal (Storage API cleanup would fail)';
 end if;
 if not exists(
  select 1 from pg_policies
  where schemaname='storage' and tablename='objects'
    and policyname='katoptron_reporter_delete_withdrawn_photos'
    and cmd='DELETE' and qual like '%withdrawn%'
 ) then raise exception 'Withdrawn-report Storage API deletion policy absent';end if;
end $qa$;
do $qa$
begin
 begin
  insert into storage.objects(bucket_id,name,owner,owner_id)
  values('katoptron-community-evidence',
  current_setting('katoptron.storage_owner')||'/'||current_setting('katoptron.storage_case')||'/evidence.png',
  current_setting('katoptron.storage_owner')::uuid,current_setting('katoptron.storage_owner'));
  raise exception 'Photo upload permitted after withdrawal';
 exception when check_violation or insufficient_privilege then null;
 end;
end $qa$;
reset role;
rollback;
