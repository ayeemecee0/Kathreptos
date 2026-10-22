-- 042: Preserve provenance across edits to already discovered .gov pages.
-- Update an unverified original-government discovery page's hash ONLY when
-- a previously staged exact GIS URL remains included in the same evidence
-- entry. The worker re-fetches the original government page and confirms
-- the unchanged live hyperlink before calling this private RPC.
create table if not exists public.government_gis_page_recheck_history (
  page_url text not null references public.government_gis_search_queue(page_url),
  page_sha256 text not null check(page_sha256 ~ '^[a-f0-9]{64}$'),
  gis_layer_url text not null,
  seen_at timestamptz not null default now(),
  primary key(page_url,page_sha256,gis_layer_url)
);
alter table public.government_gis_page_recheck_history enable row level security;
revoke all on public.government_gis_page_recheck_history
 from public,anon,authenticated,service_role;
grant select on public.government_gis_page_recheck_history to service_role;

create or replace function public.refresh_unverified_gov_gis_page_digest(
 p_page_url text,p_expected_old_sha text,
 p_current_live_sha text,p_existing_layer_url text
) returns boolean language plpgsql security definer set search_path=''
as $refresh_gov_page$
declare
  staged public.government_gis_search_queue%rowtype;
begin
  select * into staged from public.government_gis_search_queue
   where page_url=p_page_url and candidate_status='unverified' for update;
  if staged.page_url is null or
    p_expected_old_sha<>staged.page_sha256 or
    p_current_live_sha !~ '^[a-f0-9]{64}$' or
    p_expected_old_sha=p_current_live_sha or
    not staged.gis_links @> jsonb_build_array(p_existing_layer_url) or
    p_page_url !~ '^https://([a-z0-9-]+\.)+gov/.+' or
    p_existing_layer_url !~ '^https://([a-z0-9-]+\.)+gov/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+$'
  then
    raise exception 'Original government camera link or immutable evidence chain changed';
  end if;
  insert into public.government_gis_page_recheck_history(
    page_url,page_sha256,gis_layer_url
  ) values(p_page_url,staged.page_sha256,p_existing_layer_url)
   on conflict do nothing;
  update public.government_gis_search_queue set
    page_sha256=p_current_live_sha,
    last_observed_at=now()
   where page_url=p_page_url;
  insert into public.government_gis_page_recheck_history(
    page_url,page_sha256,gis_layer_url
  ) values(p_page_url,p_current_live_sha,p_existing_layer_url)
   on conflict do nothing;
  return true;
end;
$refresh_gov_page$;
revoke all on function public.refresh_unverified_gov_gis_page_digest(
 text,text,text,text) from public,anon,authenticated,service_role;
grant execute on function public.refresh_unverified_gov_gis_page_digest(
 text,text,text,text) to service_role;
