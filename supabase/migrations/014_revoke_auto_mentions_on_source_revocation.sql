-- Automatic source-trust revocation for auto-published agenda mentions.
-- If a verified government source or its approved domain authority is later
-- revoked/changed, all dependent auto-verified mentions immediately disappear
-- from the public RLS feed. Their immutable provenance remains for audit.

create or replace function public.withdraw_flock_agenda_on_source_change()
returns trigger language plpgsql security definer
set search_path = ''
as $withdraw_source$
declare
  v_tenant text;
begin
  if old.source_kind = 'legistar' and old.verification_status = 'verified'
     and (new.verification_status is distinct from 'verified'
       or new.evidence_url is distinct from old.evidence_url
       or new.jurisdiction_label is distinct from old.jurisdiction_label
       or new.source_url is distinct from old.source_url) then
    v_tenant := substring(old.source_url from
       '^https://([a-z0-9-]{3,40})\.legistar\.com/$');
    if v_tenant is not null then
      update public.verified_flock_agenda_mentions
         set status='revoked'
         where tenant=v_tenant and status='verified';
    end if;
  end if;
  return new;
end;
$withdraw_source$;

drop trigger if exists withdraw_auto_flock_agenda_on_registry_change
  on public.government_source_registry;
create trigger withdraw_auto_flock_agenda_on_registry_change
after update on public.government_source_registry
for each row execute function public.withdraw_flock_agenda_on_source_change();

create or replace function public.withdraw_flock_agenda_on_domain_change()
returns trigger language plpgsql security definer
set search_path = ''
as $withdraw_domain$
begin
  if old.verification_status = 'verified' and
    (new.verification_status is distinct from 'verified'
     or new.legistar_tenant is distinct from old.legistar_tenant
     or new.jurisdiction_label is distinct from old.jurisdiction_label
     or new.evidence_url is distinct from old.evidence_url
     or new.legistar_evidence_url is distinct from old.legistar_evidence_url) then
    update public.verified_flock_agenda_mentions
       set status='revoked'
       where tenant=old.legistar_tenant and status='verified'
         and lower(split_part(split_part(government_evidence_url,'/',3),':',1))
           in (old.domain, 'www.' || old.domain);
  end if;
  return new;
end;
$withdraw_domain$;

drop trigger if exists withdraw_auto_flock_agenda_on_domain_change
  on public.official_government_domains;
create trigger withdraw_auto_flock_agenda_on_domain_change
after update on public.official_government_domains
for each row execute function public.withdraw_flock_agenda_on_domain_change();
