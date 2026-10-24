-- Community intake is a private per-account staging interface, never publication.
do $$
begin
  if not (select relrowsecurity from pg_class where oid='public.flock_community_submissions'::regclass) then
    raise exception 'community intake missing RLS';
  end if;
  if has_table_privilege('anon','public.flock_community_submissions','INSERT')
     or has_table_privilege('anon','public.flock_community_submissions','SELECT') then
    raise exception 'anonymous community data leak';
  end if;
  if not has_column_privilege('authenticated','public.flock_community_submissions','latitude','INSERT')
     or has_column_privilege('authenticated','public.flock_community_submissions','submitter_id','INSERT')
     or has_column_privilege('authenticated','public.flock_community_submissions','report_status','UPDATE') then
    raise exception 'incorrect contributor grants';
  end if;
  if has_table_privilege('authenticated','public.flock_point_evidence_attestations','INSERT')
     or has_table_privilege('authenticated','public.flock_point_evidence_cases','UPDATE') then
    raise exception 'contributors can alter publication evidence';
  end if;
  if not exists(select 1 from pg_trigger where tgrelid='public.flock_community_submissions'::regclass
      and tgname='throttle_community_reports' and not tgisinternal) then
    raise exception 'missing abuse throttle trigger';
  end if;
end $$;
