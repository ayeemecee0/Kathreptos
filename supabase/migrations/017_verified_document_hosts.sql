-- Repair overly restrictive V1 document-host policy using observed production
-- attachment forms. Original government API binds every URL to a real Flock
-- matter. Platform-hosted PDFs require an exact tenant directory and UUID.
-- Non-platform municipal PDFs require owner-reviewed official domain bindings.
-- Never interpret documents as executed contracts.
alter table public.official_flock_contract_documents
  drop constraint if exists official_flock_contract_documents_check;

alter table public.official_flock_contract_documents
  add constraint official_contract_document_https
    check (length(document_url) between 35 and 2048
      and document_url ~ '^https://[A-Za-z0-9.-]+/[^[:space:]#]+$');

create or replace function public.is_current_government_document_url(
  p_url text, p_tenant text, p_jurisdiction_label text)
returns boolean language plpgsql stable security definer
set search_path=''
as $document_host_trust$
declare
  v_host text;
  v_path text;
  v_uuid_pattern text;
begin
  if p_url is null or p_tenant !~ '^[a-z0-9-]{3,40}$'
      or p_url !~ '^https://[A-Za-z0-9.-]+/[^[:space:]#]+$' then
    return false;
  end if;
  v_host := lower(substring(p_url from '^https://([^/]+)'));
  v_path := substring(p_url from '^https://[^/]+(/[^?#]*)');
  if v_host is null or v_path is null then
    return false;
  end if;
  if v_host = p_tenant || '.legistar.com' and
       p_url ~ ('^https://' || p_tenant ||
         '[.]legistar[.]com/View[.]ashx[?]M=F&ID=[0-9]{1,18}$') then
    return true;
  end if;
  v_uuid_pattern := '^/' || p_tenant ||
    '/attachments/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-' ||
    '[0-9a-f]{4}-[0-9a-f]{12}[.]pdf$';
  if v_host in (p_tenant || '.legistar.com',
                p_tenant || '.legistar1.com',
                'legistar.granicus.com', 'legistar1.granicus.com') then
    return v_path ~* v_uuid_pattern and p_url not like '%?%';
  end if;
  if v_path !~* '[.]pdf$' or p_url like '%?%'
      or v_path like '%..%' or v_path like '%\%' then
    return false;
  end if;
  return exists (
    select 1 from public.official_government_domains d
    where d.verification_status='verified'
      and d.legistar_tenant=p_tenant
      and d.jurisdiction_label=p_jurisdiction_label
      and (d.domain=v_host or
           (d.allow_www is true and v_host='www.' || d.domain))
  );
end;
$document_host_trust$;

create or replace function public.guard_official_flock_contract_documents()
returns trigger language plpgsql security definer set search_path=''
as $$
declare
  v_title text;
  v_label text;
  v_status text;
  v_registry_status text;
  v_registry_label text;
begin
  if tg_op='UPDATE' then
    if (new.tenant,new.matter_id,new.attachment_id,new.jurisdiction_label,
        new.matter_title,new.attachment_name,new.document_url,new.pdf_sha256,
        new.pdf_bytes,new.pdf_pages,new.verified_at,new.verification_method,
        new.execution_status)
      is distinct from
       (old.tenant,old.matter_id,old.attachment_id,old.jurisdiction_label,
        old.matter_title,old.attachment_name,old.document_url,old.pdf_sha256,
        old.pdf_bytes,old.pdf_pages,old.verified_at,old.verification_method,
        old.execution_status) then
      raise exception 'Contract document evidence is immutable';
    end if;
    if old.status='revoked' and new.status='verified' then
      raise exception 'Revoked document cannot be silently republished';
    end if;
    return new;
  end if;

  select matter_title,jurisdiction_label,status into v_title,v_label,v_status
    from public.verified_flock_agenda_mentions
    where tenant=new.tenant and matter_id=new.matter_id;
  if v_status is distinct from 'verified' or v_title is distinct from new.matter_title
      or v_label is distinct from new.jurisdiction_label then
    raise exception 'Independent government matter verification is required';
  end if;
  select verification_status,jurisdiction_label
    into v_registry_status,v_registry_label
    from public.government_source_registry
    where source_kind='legistar' and
      source_url='https://' || new.tenant || '.legistar.com/';
  if v_registry_status is distinct from 'verified'
      or v_registry_label is distinct from new.jurisdiction_label then
    raise exception 'Official government source authority is not current';
  end if;
  if not public.is_current_government_document_url(
       new.document_url,new.tenant,new.jurisdiction_label) then
    raise exception 'Document URL is not a currently approved government evidence host';
  end if;
  if new.status <> 'verified' or new.execution_status <> 'not_verified' then
    raise exception 'Document existence cannot establish contract execution';
  end if;
  return new;
end;
$$;


comment on table public.official_flock_contract_documents is
'Government agreement PDF provenance, not execution: exact verified Legistar matter and official attachment, bounded PDF, Flock agreement language and SHA-256. Platform PDF hosts are tenant-scoped; municipal PDF hosts require owner-approved authority.';
