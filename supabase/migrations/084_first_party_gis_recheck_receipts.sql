-- 084: Time-separated source-provenance health for independently reviewed
-- government GIS publishers. Unlike map point freshness, this records a fresh
-- independent original agency homepage -> mapping portal -> GIS layer proof.
-- No public caller can change receipts or create original government authority.
create table if not exists public.first_party_agency_gis_recheck_history (
 id bigint generated always as identity primary key,
 source_key text not null references public.first_party_agency_gis_receipts(source_key),
 previous_page_sha256 text not null check(previous_page_sha256 ~ '^[a-f0-9]{64}$'),
 current_page_sha256 text not null check(current_page_sha256 ~ '^[a-f0-9]{64}$'),
 previous_layer_sha256 text not null check(previous_layer_sha256 ~ '^[a-f0-9]{64}$'),
 current_layer_sha256 text not null check(current_layer_sha256 ~ '^[a-f0-9]{64}$'),
 previous_camera_count integer not null check(previous_camera_count between 1 and 250),
 current_camera_count integer not null check(current_camera_count between 1 and 250),
 observed_at timestamptz not null default now()
);
alter table public.first_party_agency_gis_recheck_history enable row level security;
revoke all on public.first_party_agency_gis_recheck_history
 from public,anon,authenticated,service_role;
grant select on public.first_party_agency_gis_recheck_history to service_role;
create index if not exists first_party_agency_rechecks_recent
 on public.first_party_agency_gis_recheck_history(source_key,observed_at desc);

-- The server verifier invokes this only AFTER independently re-fetching and
-- checking the exact original agency webpage, GIS service, twice-queried ID
-- list, full georeferenced point geometry, and prior owner-bound registry.
-- Supabase cannot independently fetch the external source inside SQL; hashes
-- are provenance attestations by an already restricted server role, NOT
-- external proof supplied by an anonymous contributor.
create or replace function public.refresh_reviewed_first_party_gis_receipt(
 p_source_key text,p_page_sha256 text,p_layer_sha256 text,
 p_camera_count integer,p_identity_basis text
) returns boolean language plpgsql security definer set search_path=''
as $refresh_first_party$
declare
 source_row public.trusted_flock_gis_sources%rowtype;
 receipt public.first_party_agency_gis_receipts%rowtype;
 root public.reviewed_first_party_gis_roots%rowtype;
begin
 if p_page_sha256 !~ '^[a-f0-9]{64}$'
    or p_layer_sha256 !~ '^[a-f0-9]{64}$'
    or p_camera_count not between 1 and 250
    or p_identity_basis not in ('arcgis_typed_objectid','named_camera_id')
 then raise exception 'Fresh original government GIS attestation malformed';end if;

 select * into root from public.reviewed_first_party_gis_roots
   where source_key=p_source_key and review_status='verified';
 select * into source_row from public.trusted_flock_gis_sources
   where source_key=p_source_key and source_status='verified';
 select * into receipt from public.first_party_agency_gis_receipts
   where source_key=p_source_key for update;
 if root.source_key is null or source_row.source_key is null
    or receipt.source_key is null
    or root.gis_layer_url<>source_row.gis_layer_url
    or root.agency_page_url<>source_row.government_evidence_url
    or root.jurisdiction_label<>source_row.jurisdiction_label
    or root.agency_page_url<>receipt.agency_page_url
    or root.agency_portal_url<>receipt.agency_portal_url
    or receipt.identity_basis<>p_identity_basis
 then raise exception 'Reviewed original government publisher no longer independently approved';end if;
 insert into public.first_party_agency_gis_recheck_history(
   source_key,previous_page_sha256,current_page_sha256,
   previous_layer_sha256,current_layer_sha256,
   previous_camera_count,current_camera_count
 ) values(
   p_source_key,receipt.original_page_sha256,p_page_sha256,
   receipt.full_layer_points_sha256,p_layer_sha256,
   receipt.original_camera_count,p_camera_count
 );
 update public.first_party_agency_gis_receipts
   set original_page_sha256=p_page_sha256,
       full_layer_points_sha256=p_layer_sha256,
       original_camera_count=p_camera_count,
       confirmed_at=now()
 where source_key=p_source_key;
 return true;
end
$refresh_first_party$;
revoke all on function public.refresh_reviewed_first_party_gis_receipt(
 text,text,text,integer,text) from public,anon,authenticated,service_role;
grant execute on function public.refresh_reviewed_first_party_gis_receipt(
 text,text,text,integer,text) to service_role;
comment on function public.refresh_reviewed_first_party_gis_receipt(text,text,text,integer,text) is
'Existing owner-reviewed government GIS source only: append private independent original-page and ArcGIS inventory recheck receipt and advance freshness; cannot create authorities or change an identity basis.';
