"""Conservatively verify candidate Legistar tenants using official government evidence.

Verification requires a pre-existing evidence_url on a .gov page that explicitly
links to the same Legistar tenant and names the registry jurisdiction. No ALPR
agenda matter is published by this script.
"""
import html.parser
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.request
from government_domain_registry import (
    approved_tenant_for_page, load_approved_domains,
    official_url, public_dns, trusted_domain_row, valid_https_url,
)

BASE_HEADERS = {"User-Agent": "Katoptron/1.0 public records research", "Accept": "application/json"}
TENANT = re.compile(r"^([a-z0-9-]{3,40})\.legistar\.com$", re.I)
MAX_ROWS = 100


class LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.text_parts = []
        self.in_title = False
        self.title_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        self.text_parts.append(data)
        if self.in_title:
            self.title_parts.append(data)


def supabase_request(path, method="GET", payload=None):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": "Bearer " + key,
               "Accept": "application/json", "Content-Type": "application/json"}
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + "/rest/v1/" + path, data=data,
                                 headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Supabase response too large")
    return json.loads(raw) if raw else None


def safe_official_url(url, approved):
    normalized = official_url(url, approved)
    return bool(normalized and public_dns(urllib.parse.urlsplit(normalized).hostname))


class SafeGovernmentRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, approved, original_host):
        super().__init__()
        self.approved = approved
        self.original_host = original_host
        self.original_row = trusted_domain_row(original_host, approved)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        normalized = official_url(newurl, self.approved)
        if not normalized:
            raise ValueError("Evidence redirect leaves approved government domains")
        host = urllib.parse.urlsplit(normalized).hostname
        new_row = trusted_domain_row(host, self.approved)
        if self.original_row:
            if new_row is not self.original_row:
                raise ValueError("Evidence redirects to a different government authority")
        elif not host.endswith(".gov"):
            raise ValueError(".gov evidence redirected to an unrelated custom domain")
        if not public_dns(host):
            raise ValueError("Evidence redirect host does not resolve publicly")
        return super().redirect_request(req, fp, code, msg, headers, normalized)


def fetch_official_html(url, approved):
    normalized = official_url(url, approved)
    if not normalized or not safe_official_url(normalized, approved):
        raise ValueError("Evidence URL is not an approved public government HTTPS page")
    original_host = urllib.parse.urlsplit(normalized).hostname
    opener = urllib.request.build_opener(SafeGovernmentRedirect(approved, original_host))
    req = urllib.request.Request(normalized, headers={
        "User-Agent": BASE_HEADERS["User-Agent"], "Accept": "text/html"})
    with opener.open(req, timeout=12) as response:
        final_url = official_url(response.geturl(), approved)
        if not final_url:
            raise ValueError("Evidence final URL is not trusted")
        ctype = response.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype:
            raise ValueError("Evidence is not HTML")
        raw = response.read(500_001)
    if len(raw) > 500_000:
        raise ValueError("Evidence page too large")
    return raw.decode("utf-8", errors="replace"), final_url


def valid_tenant_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        return None
    match = TENANT.fullmatch((parts.hostname or "").lower())
    return match.group(1).lower() if match else None


def legistar_api_valid(tenant):
    url = "https://webapi.legistar.com/v1/" + tenant + "/matters?%24top=1"
    req = urllib.request.Request(url, headers=BASE_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = response.read(100_001)
    if len(raw) > 100_000:
        return False
    data = json.loads(raw)
    return isinstance(data, list)


def verify(row, approved):
    source_url = str(row.get("source_url") or "")
    evidence_url = str(row.get("evidence_url") or "")
    label = str(row.get("jurisdiction_label") or "").strip()
    tenant = valid_tenant_url(source_url)
    if not tenant or not evidence_url or not label or label.lower().startswith("legistar tenant"):
        return False, "missing or invalid tenant, evidence URL, or jurisdiction label"
    if not safe_official_url(evidence_url, approved):
        return False, "evidence URL is not an approved public government domain"
    approved_binding = trusted_domain_row(
        urllib.parse.urlsplit(evidence_url).hostname or "", approved)
    if approved_binding:
        matched_label = approved_tenant_for_page(evidence_url, tenant, approved)
        if not matched_label or matched_label.casefold() != label.casefold():
            return False, "custom government domain is not approved for this tenant and jurisdiction"
    document = LinkParser()
    raw_html, final_url = fetch_official_html(evidence_url, approved)
    document.feed(raw_html)
    matched = False
    for href in document.links:
        target = urllib.parse.urljoin(final_url, href)
        if valid_tenant_url(target) == tenant:
            matched = True
            break
    if not matched:
        return False, "official page does not link to this Legistar tenant"
    # An official page linking to a tenant alone does not establish that the
    # page represents the registry's claimed jurisdiction.
    visible = " ".join(document.text_parts).lower()
    title = " ".join(document.title_parts).lower()
    name = label.split(",", 1)[0].strip().lower()
    if len(name) < 4 or name not in visible and name not in title:
        return False, "jurisdiction name not found on official page"
    if not legistar_api_valid(tenant):
        return False, "Legistar API returned unexpected data"
    return True, "reviewed government site links to tenant and identifies jurisdiction"


def main():
    approved = load_approved_domains()
    print("Explicitly verified custom government domains loaded:", len(approved))
    params = urllib.parse.urlencode({"select": "source_url,evidence_url,jurisdiction_label,source_kind,verification_status",
                                     "source_kind": "eq.legistar", "verification_status": "eq.candidate",
                                     "limit": str(MAX_ROWS)})
    rows = supabase_request("government_source_registry?" + params)
    if not isinstance(rows, list):
        raise ValueError("Unexpected registry response")
    print("Legistar registry candidates checked:", len(rows))
    promoted = 0
    for row in rows:
        try:
            ok, reason = verify(row, approved)
            if not ok:
                print("Candidate retained:", str(row.get("source_url") or "")[:100], "-", reason)
                continue
            source_url = str(row["source_url"])
            query = urllib.parse.urlencode({"source_url": "eq." + source_url,
                                            "source_kind": "eq.legistar",
                                            "verification_status": "eq.candidate"})
            supabase_request("government_source_registry?" + query, method="PATCH",
                             payload={"verification_status": "verified"})
            promoted += 1
            print("Verified tenant:", source_url)
        except Exception as exc:
            print("Candidate verification unavailable:", type(exc).__name__, str(exc)[:140])
    print("Newly verified Legistar tenants:", promoted)
    print("Agenda records auto-published: 0")


if __name__ == "__main__":
    main()
