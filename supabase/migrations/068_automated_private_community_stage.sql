-- 068: Automated *private staging*, never self-certification.
-- Reporters cannot set case classification or evidence review status.
create function katoptron_internal.stage_submitted_camera_candidate()
returns trigger language plpgsql security definer set search_path=''
as $$
declare k text;
begin
 if new.original_source_url is null then return new; end if;
 k:='tier_'||md5(new.submission_id::text);
 insert into public.flock_point_evidence_cases
 (case_key,label,jurisdiction_label,latitude,longitude,evidence_summary,source_url)
 values(k,'Community-reported possible Flock device','Community report; jurisdiction unverified',
  new.latitude,new.longitude,left('Unverified community camera report. '||new.description,1500),
  new.original_source_url)
 on conflict(case_key) do nothing;
 insert into public.flock_point_evidence_attestations
 (evidence_key,case_key,source_kind,source_family,source_url,latitude,longitude,evidence_sha256,source_excerpt)
 values('proof_'||md5(new.submission_id::text),k,'community_report','katoptron.community',
  new.original_source_url,new.latitude,new.longitude,
  encode(sha256(convert_to(new.description||'|'||new.original_source_url||'|'||new.latitude::text||'|'||new.longitude::text,'UTF8')),'hex'),
  left(new.description,900))
 on conflict(evidence_key) do nothing;
 return new;
end $$;
revoke all on function katoptron_internal.stage_submitted_camera_candidate() from public,anon,authenticated;
create trigger private_auto_stage_community_camera
after insert on public.flock_community_submissions
for each row execute function katoptron_internal.stage_submitted_camera_candidate();

-- Rejected / withdrawn reports must invalidate their underlying candidate.
create function katoptron_internal.revoke_rejected_community_evidence()
returns trigger language plpgsql security definer set search_path=''
as $$
declare k text;
begin
 if new.report_status in ('rejected','withdrawn') and new.report_status is distinct from old.report_status then
  k:='tier_'||md5(new.submission_id::text);
  update public.flock_point_evidence_attestations
   set evidence_status=case when new.report_status='rejected' then 'rejected' else 'withdrawn' end
   where evidence_key='proof_'||md5(new.submission_id::text)
     and case_key=k and source_kind='community_report';
  update public.flock_point_evidence_cases
   set classification=case when new.report_status='rejected' then 'rejected' else 'withdrawn' end
   where case_key=k;
 end if;
 return new;
end $$;
revoke all on function katoptron_internal.revoke_rejected_community_evidence() from public,anon,authenticated;
create trigger private_revoke_community_rejection
after update of report_status on public.flock_community_submissions
for each row execute function katoptron_internal.revoke_rejected_community_evidence();
