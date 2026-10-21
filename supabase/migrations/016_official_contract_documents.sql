-- Government-hosted Flock Safety agreement documents, NOT executed contracts.
-- A PDF is eligible only after fresh independent validation of the parent
-- government Legistar matter and actual bounded PDF text. Execution, signatures,
-- payment and deployment are NOT represented by this table.
create table if not exists public.official_flock_contract_documents (
  tenant text not null check (tenant ~ '^[a-z0-9-]{3,40}$'),
  matter_id bigint not null check (matter_id > 0),
  attachment_id bigint not null check (attachment_id > 0),
  jurisdiction_label text not null check (length(btrim(jurisdiction_label)) between 5 and 150),
  matter_title text not null check (length(btrim(matter_title)) between 12 and 1000 and
    matter_title ~* 'flock[[:space:][:punct:]]+safety'),
  attachment_name text not null check (length(btrim(attachment_name)) between 4 and 240),
  document_url text not null check (length(document_url) between 35 and 2048 and
    document_url like 'https://' || tenant || '.legistar.com/%'),
  pdf_sha256 text not null check (pdf_sha256 ~ '^[0-9a-f]{64}$'),
  pdf_bytes integer not null check (pdf_bytes between 200 and 8388608),
  pdf_pages integer not null check (pdf_pages between 1 and 60),
  verified_at timestamptz not null default now(),
  verification_method text not null default 'official_legistar_agreement_pdf_exact_vendor_text_v1'
    check (verification_method = 'official_legistar_agreement_pdf_exact_vendor_text_v1'),
  execution_status text not null default 'not_verified'
    check (execution_status = 'not_verified'),
  status text not null default 'verified' check (status in ('verified','revoked')),
  primary key (tenant,matter_id,attachment_id),
  foreign key (tenant,matter_id)
    references public.verified_flock_agenda_mentions(tenant,matter_id) on delete restrict
);
create index if not exists official_flock_contract_documents_time_idx
  on public.official_flock_contract_documents (verified_at desc,tenant);

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
  if new.status <> 'verified' or new.execution_status <> 'not_verified' then
    raise exception 'Document existence cannot establish contract execution';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_official_flock_contract_documents
 on public.official_flock_contract_documents;
create trigger guard_official_flock_contract_documents
before insert or update on public.official_flock_contract_documents
for each row execute function public.guard_official_flock_contract_documents();

create or replace function public.revoke_contract_documents_with_parent()
returns trigger language plpgsql security definer set search_path=''
as $$
begin
  if old.status='verified' and new.status='revoked' then
    update public.official_flock_contract_documents set status='revoked'
      where tenant=old.tenant and matter_id=old.matter_id and status='verified';
  end if;
  return new;
end;
$$;
drop trigger if exists revoke_contract_documents_with_parent
 on public.verified_flock_agenda_mentions;
create trigger revoke_contract_documents_with_parent
after update on public.verified_flock_agenda_mentions
for each row execute function public.revoke_contract_documents_with_parent();

alter table public.official_flock_contract_documents enable row level security;
revoke all on public.official_flock_contract_documents from anon,authenticated,service_role;
grant select on public.official_flock_contract_documents to anon,authenticated;
grant select,insert on public.official_flock_contract_documents to service_role;
grant update(status) on public.official_flock_contract_documents to service_role;

drop policy if exists public_official_flock_contract_documents
  on public.official_flock_contract_documents;
create policy public_official_flock_contract_documents
  on public.official_flock_contract_documents for select to anon,authenticated
  using (status='verified' and exists (
    select 1 from public.verified_flock_agenda_mentions m
      where m.tenant=official_flock_contract_documents.tenant
        and m.matter_id=official_flock_contract_documents.matter_id
        and m.status='verified'
  ));

comment on table public.official_flock_contract_documents is
'Exact government-hosted original PDF documents with verified Flock Safety agreement language. These are source documents, not independently verified signed or executed agreements.';
