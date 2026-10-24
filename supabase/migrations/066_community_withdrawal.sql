-- 066: Report withdrawal immediately revokes linked private source evidence.
-- No direct public update privileges are granted.
create function public.withdraw_own_community_report(p_id uuid)
returns boolean language plpgsql security definer set search_path='' as $$
declare s public.flock_community_submissions%rowtype;
 ckey text;
 ekey text;
begin
 if auth.uid() is null then raise exception 'Sign in required' using errcode='42501'; end if;
 select * into s from public.flock_community_submissions
 where submission_id=p_id and submitter_id=auth.uid() for update;
 if not found then return false; end if;
 if s.report_status='withdrawn' then return true; end if;
 ckey:='tier_'||md5(p_id::text);
 ekey:='proof_'||md5(p_id::text);
 update public.flock_community_submissions set report_status='withdrawn' where submission_id=p_id;
 update public.flock_point_evidence_attestations set evidence_status='withdrawn'
 where evidence_key=ekey and case_key=ckey and source_kind='community_report';
 update public.flock_point_evidence_cases set classification='withdrawn'
 where case_key=ckey;
 return true;
end $$;
revoke all on function public.withdraw_own_community_report(uuid) from public,anon,authenticated;
grant execute on function public.withdraw_own_community_report(uuid) to authenticated;
