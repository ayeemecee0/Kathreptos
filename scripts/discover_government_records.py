"""Discover ALPR-related public Legistar agenda matters from verified registry tenants.

Matches are queued privately for manual review, never published automatically.
"""
import concurrent.futures
import json
import os
import re
import urllib.parse
import urllib.request
from government_domain_registry import (
    approved_tenant_for_page, gov_host, load_approved_domains, valid_https_url,
)

TERMS = re.compile(r"\b(?:flock\s+safety|automated?\s+license\s+plate\s+readers?|ALPR|LPR\s+cameras?)\b", re.I)
TENANT = re.compile(r"([a-z0-9-]{3,40})\.legistar\.com", re.I)
USER_AGENT = "Katoptron/1.0 public records research"
LEGACY_PREAPPROVED = {"seattle", "lacounty", "costamesa", "oakland"}


def get_json(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {
        "User-Agent": USER_AGENT, "Accept": "application/json"
    })
    with urllib.request.urlopen(request, timeout=12) as response:
        data = response.read(1500001)
    if len(data) > 1500000:
        raise ValueError("API response too large")
    return json.loads(data)


def registry_clients():
    """Fail closed: load only verified tenants with current domain approval."""
    approved = load_approved_domains()
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    params = urllib.parse.urlencode({
        "select": "source_url,host,jurisdiction_label,evidence_url",
        "source_kind": "eq.legistar",
        "verification_status": "eq.verified",
        "limit": "1000",
    })
    rows = get_json(base + "/rest/v1/government_source_registry?" + params, {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
    })
    if not isinstance(rows, list):
        raise ValueError("Unexpected registry response")
    clients = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source_url") or "")
        parsed = urllib.parse.urlsplit(source)
        host = (parsed.hostname or "").lower()
        match = TENANT.fullmatch(host)
        if parsed.scheme != "https" or not match or parsed.username or parsed.password:
            print("Registry entry skipped: invalid Legistar URL")
            continue
        try:
            port = parsed.port
        except ValueError:
            continue
        if port not in (None, 443):
            continue
        label = str(row.get("jurisdiction_label") or "").strip()
        if not label or label.lower().startswith("legistar tenant "):
            print("Registry entry skipped: unverified jurisdiction label", host)
            continue
        evidence = str(row.get("evidence_url") or "")
        parsed_evidence = valid_https_url(evidence)
        # Legacy manually preapproved seeds record their tenant portal as evidence;
        # .gov evidence relies on the existing official-government verification.
        # For custom domains, source authority MUST still be approved today.
        client_code = match.group(1).lower()
        legacy_proof = (client_code in LEGACY_PREAPPROVED and
                        evidence.lower().rstrip("/") ==
                        "https://" + host)
        if not parsed_evidence:
            print("Registry entry skipped: missing trusted evidence URL", host)
            continue
        if gov_host(parsed_evidence.hostname):
            # Ordinary .gov evidence is valid when the domain, Legistar
            # tenant and jurisdiction all agree. Abbreviated/alternative
            # names such as cabq or cook-county need a CURRENT explicitly
            # reviewed binding, and are skipped if that binding is revoked.
            government_stem = parsed_evidence.hostname.rsplit(".", 2)[-2].lower()
            normalized_label = re.sub(
                r"[^a-z0-9]", "", label.split(",", 1)[0].lower())
            normalized_tenant = re.sub(r"[^a-z0-9]", "", client_code)
            if not (normalized_tenant == normalized_label == government_stem):
                current_label = approved_tenant_for_page(evidence, client_code, approved)
                if current_label != label:
                    print("Registry entry skipped: unapproved government tenant alias", host)
                    continue
        elif legacy_proof:
            pass  # Known four manually reviewed Legistar tenants only
        else:
            current_label = approved_tenant_for_page(evidence, client_code, approved)
            if current_label != label:
                print("Registry entry skipped: custom domain authority revoked or mismatched", host)
                continue
        clients[client_code] = label[:150]
    return clients


def enrich(client, mid):
    base = "https://webapi.legistar.com/v1/" + client + "/matters/" + str(mid)
    notes = []
    try:
        histories = get_json(base + "/histories")
        if isinstance(histories, list):
            for item in histories[:5]:
                name = str(item.get("MatterHistoryActionName") or "")
                date = str(item.get("MatterHistoryActionDate") or "")[:10]
                body = str(item.get("MatterHistoryActionBodyName") or "")
                if name:
                    notes.append("Action: " + name[:65] + " (" + date + ", " + body[:45] + ")")
    except Exception as exc:
        notes.append("Action history unavailable: " + type(exc).__name__)
    try:
        attachments = get_json(base + "/attachments")
        if isinstance(attachments, list):
            names = [str(item.get("MatterAttachmentName") or "")[:65] for item in attachments[:4]]
            notes.append("Attachments listed: " + ("; ".join(names) if names else "none"))
    except Exception as exc:
        notes.append("Attachments unavailable: " + type(exc).__name__)
    return " | ".join(notes)


def scan(client, label):
    url = "https://webapi.legistar.com/v1/" + client + "/matters?%24top=250&%24orderby=MatterId%20desc"
    rows = get_json(url)
    if not isinstance(rows, list):
        raise ValueError("Unexpected Legistar API response")
    leads = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        body = " ".join(str(row.get(k) or "") for k in ("MatterName", "MatterTitle", "MatterTypeName"))
        if not TERMS.search(body):
            continue
        mid = row.get("MatterId")
        if type(mid) is not int or mid < 1:
            continue
        link = "https://" + client + ".legistar.com/LegislationDetail.aspx?ID=" + str(mid)
        details = enrich(client, mid)
        leads.append({
            "url": link,
            "headline": str(row.get("MatterName") or "Government ALPR agenda matter")[:300],
            "publisher": label,
            "snippet": ("Official public agenda matter; manual source verification required. " + body + " | " + details)[:500],
            "status": "unreviewed",
        })
    return leads


def queue(lead):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    request = urllib.request.Request(
        base + "/rest/v1/discovery_queue?on_conflict=url",
        data=json.dumps([lead]).encode("utf-8"), method="POST",
        headers={
            "apikey": key, "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.status


def main():
    clients = registry_clients()  # No candidate-file or hardcoded fallback.
    print("Verified Legistar tenants loaded from registry:", len(clients))
    all_leads = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tasks = {pool.submit(scan, client, label): client for client, label in clients.items()}
        for task in concurrent.futures.as_completed(tasks):
            client = tasks[task]
            try:
                matches = task.result()
                all_leads.extend(matches)
                print("Official agenda matches:", client, len(matches))
            except Exception as exc:
                print("Official agenda source unavailable:", client, type(exc).__name__, str(exc)[:120])
    unique = {lead["url"]: lead for lead in all_leads}
    print("Unique official agenda leads:", len(unique))
    queued = 0
    for lead in unique.values():
        try:
            queue(lead)
            queued += 1
        except Exception as exc:
            print("Agenda queue error:", type(exc).__name__, str(exc)[:120])
    print("Official agenda leads queued:", queued)
    print("Agenda records auto-published: 0 (review required)")


if __name__ == "__main__":
    main()
