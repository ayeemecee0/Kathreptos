-- 038: If a verified government's original Flock disclosure is successfully
-- retrieved but no longer links the same externally hosted layer, revoke
-- the endorsement and downstream verified camera records. A transient HTTP
-- outage must not be treated as removal; the caller only invokes after a
-- successful live HTML page read with a changed source digest.
create or replace function public.revoke_external_flock_endorsement_after_link_loss(
 p_source_key text,p_current_page_sha256 text
) returns boolean language plpgsql security definer set search_path=''
as $ext_gis_link_revoke$
declare
  authority public.official_external_flock_gis_authorities%rowtype;
begin
  select * into authority from public.official_external_flock_gis_authorities
   where source_key=p_source_key and verification_status='verified' for update;
  if authority.source_key is null or
     p_current_page_sha256 !~ '^[a-f0-9]{64}$' or
     p_current_page_sha256=authority.original_page_sha256 then
     raise exception 'Original source change is not independently evidenced';
  end if;
  update public.official_external_flock_gis_authorities
   set verification_status='revoked' where source_key=p_source_key;
  update public.trusted_flock_gis_sources
   set source_status='revoked'
   where source_key=p_source_key and source_status='verified';
  return true;
end;
$ext_gis_link_revoke$;
revoke all on function public.revoke_external_flock_endorsement_after_link_loss(text,text)
 from public,anon,authenticated,service_role;
grant execute on function public.revoke_external_flock_endorsement_after_link_loss(text,text)
 to service_role;
