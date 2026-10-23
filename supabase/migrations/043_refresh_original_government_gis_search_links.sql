-- 043: retain new direct GIS service/layer links from revisited .gov Flock disclosures.
-- A search result or a government page is not, by itself, camera authority.
-- This narrow service-role-only RPC requires the exact previously observed
-- page digest and a newly observed current original-government HTML digest.
create or replace function public.refresh_original_government_gis_search_lead(
 p_page_url text,p_expected_previous_sha text,p_current_page_sha text,
 p_gis_links jsonb
) returns boolean language plpgsql security definer set search_path=''
as $refresh_original_gis$
declare
 lead public.government_gis_search_queue%rowtype;
 entry jsonb;
 url text;
begin
 select * into lead
 from public.government_gis_search_queue
 where page_url=p_page_url and candidate_status='unverified'
 for update;
 if lead.page_url is null
   or p_page_url !~ '^https://([a-z0-9-]+\.)+gov/.+'
   or lead.page_sha256<>p_expected_previous_sha
   or p_current_page_sha !~ '^[a-f0-9]{64}$'
   or jsonb_typeof(p_gis_links)<>'array'
   or jsonb_array_length(p_gis_links)>25 then
    raise exception 'Original government camera-page evidence refresh denied';
 end if;
 for entry in select value from jsonb_array_elements(p_gis_links) as value
 loop
   if jsonb_typeof(entry)<>'string' then
     raise exception 'Original government GIS link is not a URL string';
   end if;
   url:=entry #>> '{}';
   if length(url)>1500 or
     url !~ '^https://([a-z0-9-]+\.)+[a-z0-9-]+/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)(/[0-9]+)?$'
   then raise exception 'Original government GIS link is not a safe public ArcGIS service or layer URL';
   end if;
 end loop;
 if (select count(*) from jsonb_array_elements_text(p_gis_links)) <>
    (select count(distinct value) from jsonb_array_elements_text(p_gis_links) as value)
 then
   raise exception 'Original government GIS link observation duplicated';
 end if;

 -- Keep old and new digests for source revision investigations; do not
 -- infer that former links are still endorsed by the live government page.
 insert into public.government_gis_page_recheck_history(
   page_url,page_sha256,gis_layer_url)
 select lead.page_url,lead.page_sha256,value
 from jsonb_array_elements_text(lead.gis_links) as value
 on conflict do nothing;

 update public.government_gis_search_queue
    set page_sha256=p_current_page_sha,
        gis_links=p_gis_links,
        last_observed_at=now()
 where page_url=p_page_url and candidate_status='unverified';

 insert into public.government_gis_page_recheck_history(
   page_url,page_sha256,gis_layer_url)
 select p_page_url,p_current_page_sha,value
 from jsonb_array_elements_text(p_gis_links) as value
 on conflict do nothing;
 return true;
end;
$refresh_original_gis$;
revoke all on function public.refresh_original_government_gis_search_lead(
 text,text,text,jsonb) from public,anon,authenticated,service_role;
grant execute on function public.refresh_original_government_gis_search_lead(
 text,text,text,jsonb) to service_role;

comment on function public.refresh_original_government_gis_search_lead(text,text,text,jsonb)
is 'Service-role-only update of previously verified original .gov Flock-page link observations; stores immutable old/new digest history. Not a source promotion or publication API.';
