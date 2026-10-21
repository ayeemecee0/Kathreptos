"""Approved government domain authorities, with explicit jurisdiction/Legistar bindings.

Only rows explicitly reviewed and marked verified in the PRIVATE Supabase table
can authorize a non-.gov host or grant a .gov tenant-name exception.
Discovery may never approve a new domain or tenant binding.
"""
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.request

DOMAIN_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
TENANT_RE = re.compile(r"^[a-z0-9-]{3,40}$")
CUSTOM_SUFFIXES = (".com", ".org", ".net", ".us", ".gov")


def public_dns(host):
    """Reject private/reserved destinations before any outside request."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(record[4][0]).is_global for record in addresses)
    except (OSError, ValueError):
        return False


def valid_https_url(url):
    """Return parsed HTTPS URL, or None for credentials, ports, or invalid hosts."""
    try:
        parts = urllib.parse.urlsplit(str(url).strip())
        host = (parts.hostname or "").lower()
        if (parts.scheme.lower() != "https" or not host or
                parts.username or parts.password or parts.port not in (None, 443) or
                "\\" in str(url) or not DOMAIN_RE.fullmatch(host)):
            return None
        return parts
    except (ValueError, AttributeError):
        return None


def gov_host(host):
    return host.endswith(".gov") and host != ".gov"


def trusted_domain_row(host, approved):
    """No wildcard/suffix matching: only registered apex or explicitly allowed www."""
    host = (host or "").lower()
    row = approved.get(host)
    if row:
        return row
    if host.startswith("www."):
        row = approved.get(host[4:])
        if row and row["allow_www"]:
            return row
    return None


def official_url(url, approved):
    """Accept .gov sites and explicitly approved custom domains, HTTPS only."""
    parts = valid_https_url(url)
    if parts is None:
        return None
    host = parts.hostname.lower()
    if not gov_host(host) and trusted_domain_row(host, approved) is None:
        return None
    value = urllib.parse.urlunsplit(("https", host, parts.path or "/", parts.query, ""))
    return value if len(value) <= 1000 else None


def approved_tenant_for_page(page_url, tenant, approved):
    """Return approved identity ONLY for a custom domain paired with this tenant."""
    parts = valid_https_url(page_url)
    if parts is None:
        return None
    row = trusted_domain_row(parts.hostname, approved)
    if row is None or row["legistar_tenant"] != tenant:
        return None
    return row["jurisdiction_label"]


def approved_evidence_pages(approved):
    """Only operator-reviewed URLs, not arbitrary search results, become crawl seeds."""
    pages = []
    for row in approved.values():
        url = row.get("legistar_evidence_url")
        if url and official_url(url, approved):
            host = valid_https_url(url).hostname
            if trusted_domain_row(host, approved) is row:
                pages.append(url)
    return sorted(set(pages))


def parse_verified_rows(rows):
    if not isinstance(rows, list):
        raise ValueError("Unexpected domain registry response")
    approved = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("verification_status") != "verified":
            continue
        domain = str(row.get("domain") or "").strip().lower()
        tenant = str(row.get("legistar_tenant") or "").strip().lower()
        label = str(row.get("jurisdiction_label") or "").strip()
        evidence = valid_https_url(row.get("evidence_url") or "")
        if (not DOMAIN_RE.fullmatch(domain) or not domain.endswith(CUSTOM_SUFFIXES)
                or not TENANT_RE.fullmatch(tenant) or len(label) < 5
                or not evidence or not gov_host(evidence.hostname)
                or not str(row.get("reviewed_by") or "").strip() or not row.get("reviewed_at")
                or type(row.get("allow_www")) is not bool):
            raise ValueError("Invalid reviewed government-domain authority row: " + domain[:80])
        page = row.get("legistar_evidence_url")
        if page is not None:
            parsed = valid_https_url(page)
            if parsed is None or parsed.hostname not in (
                    domain, "www." + domain if row["allow_www"] else domain):
                raise ValueError("Evidence page is outside its reviewed domain: " + domain)
        if domain in approved:
            raise ValueError("Duplicate reviewed government domain: " + domain)
        approved[domain] = {
            "domain": domain, "jurisdiction_label": label,
            "legistar_tenant": tenant, "allow_www": row["allow_www"],
            "legistar_evidence_url": page,
        }
    return approved


def load_approved_domains():
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    params = urllib.parse.urlencode({
        "select": ("domain,jurisdiction_label,legistar_tenant,legistar_evidence_url,"
                   "allow_www,verification_status,evidence_url,reviewed_by,reviewed_at"),
        "verification_status": "eq.verified", "limit": "500",
    })
    url = base + "/rest/v1/official_government_domains?" + params
    req = urllib.request.Request(url, headers={
        "apikey": key, "Authorization": "Bearer " + key,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(200_001)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 406):
            raise RuntimeError(
                "Official-domain registry is unavailable. Apply Supabase migration 003 "
                "in the SQL Editor, then rerun the workflow.") from exc
        raise
    if len(raw) > 200_000:
        raise ValueError("Official-domain registry response too large")
    return parse_verified_rows(json.loads(raw))
