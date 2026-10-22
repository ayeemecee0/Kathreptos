-- 040: The newly automated .gov Flock GIS roots remain verified only
-- while their original government camera disclosures still directly link
-- the specific layer. A changed, successfully retrieved document with the
-- link missing triggers the existing root->source->camera revocation chain.
create or replace function public.revoke_auto_gov_flock_source_after_link_loss(
 p_source_key text,p_current_page_sha256 text
) returns boolean language plpgsql security definer set search_path=''
as $autogov_revoke$
declare
  authority public.auto_discovered_government_flock_gis%rowtype;
  root public.gis_government_host_authorities%rowtype;
begin
  select * into authority from public.auto_discovered_government_flock_gis
   where source_key=p_source_key for update;
  select * into root from public.gis_government_host_authorities
   where authority_key=p_source_key and verification_status='verified' for update;
  if authority.source_key is null or root.authority_key is null or
     p_current_page_sha256 !~ '^[a-f0-9]{64}$' or
     p_current_page_sha256=authority.original_page_sha256 or
     authority.government_page_url<>root.official_government_page then
    raise exception 'Original government camera-source withdrawal not independently verified';
  end if;
  update public.gis_government_host_authorities
   set verification_status='revoked'
   where authority_key=p_source_key and verification_status='verified';
  return true;
end;
$autogov_revoke$;
revoke all on function public.revoke_auto_gov_flock_source_after_link_loss(text,text)
 from public,anon,authenticated,service_role;
grant execute on function public.revoke_auto_gov_flock_source_after_link_loss(text,text)
 to service_role;
