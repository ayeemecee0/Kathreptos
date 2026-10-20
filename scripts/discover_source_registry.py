"""Discover government portals and persist candidates in a private Supabase registry.

Search-result mentions are NEVER sufficient to verify jurisdiction or publish records.
Only preapproved Legistar tenants are verified automatically. All other entries are
candidates requiring explicit source-to-jurisdiction verification.
"""
import concurrent.futures
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SEEDS = {"costamesa":"Costa Mesa, CA","oakland":"Oakland, CA",
         "seattle":"Seattle, WA","lacounty":"Los Angeles County, CA"}
QUERIES = [
    'site:.gov "legistar.com" "agenda"',
    'site:.gov "legistar.com" "city council"',
    'site:.gov "legistar.com" "meetings"',
    'site:.gov "Legistar" "legislation"',
    '"Flock Safety" "legistar.com"',
    '"license plate reader" "legistar.com"',
    '"Flock Safety" "city council" "legistar"',
    '"Flock Safety" "agenda" site:gov',
    '"automated license plate reader" "procurement" site:gov',
    '"Flock Safety" "transparency" site:gov',
]
OFFICIAL_NAME = re.compile(
    r"\b(?:City and County|City|Town|Village|County|Borough|Township|Parish) of "
    r"([A-Za-z][A-Za-z .'-]{2,75})$", re.I)
SITE_SUFFIX = re.compile(r"\s+(?:official (?:website|site)|government website|home page|homepage)$", re.I)
FOLLOW_TERMS = ("agenda", "meeting", "council", "legislation", "legistar", "board", "calendar")
MAX_GOV_PAGES = 48
MAX_SEED_PAGES = 30
MAX_FOLLOW_PER_PAGE = 2
MAX_BYTES = 500_000
USER_AGENT = "Katoptron/1.0 public records research"
STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
ABBREVIATIONS = set(STATE_CODES.values())
LEGISTAR = re.compile(r"https?://([a-z0-9-]{3,40})\.legistar\.com(?:/|\b)",re.I)
GOV = re.compile(r"https?://[a-z0-9.-]+\.gov(?:/[^\s<>\"']*)?",re.I)

def rss(query):
    url="https://www.bing.com/search?format=rss&q="+urllib.parse.quote(query)
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=9) as response:
        data=response.read(350000)
    root=ET.fromstring(data)
    return [(item.findtext("link") or "",item.findtext("description") or "")
            for item in root.findall(".//item")]

def candidate(url,kind,label=None,status="candidate",evidence=None):
    p=urllib.parse.urlsplit(url)
    host=(p.hostname or "").lower()
    if p.scheme!="https" or not host or p.username or p.password or p.port not in (None,443):
        return None
    if kind=="legistar" and not re.fullmatch(r"[a-z0-9-]{3,40}\.legistar\.com",host):
        return None
    if kind!="legistar" and not host.endswith(".gov"):
        return None
    normalized="https://"+host+(p.path or "/")
    return {"source_url":normalized[:1000],"host":host,"source_kind":kind,
            "jurisdiction_label":label,"verification_status":status,
            "evidence_url":evidence}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirected government page requires manual review")


class GovernmentPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.branding = []
        self._title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append((attributes["href"], attributes.get("title") or ""))
        if tag == "title":
            self._title = True
        if tag == "meta":
            name = (attributes.get("property") or attributes.get("name") or "").lower()
            if name in ("og:site_name", "application-name"):
                self.branding.append(attributes.get("content") or "")

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False

    def handle_data(self, data):
        if self._title:
            self._title_parts.append(data)

    def close(self):
        super().close()
        self.branding.append(" ".join(self._title_parts))


def official_url(url):
    """Only accept public HTTPS .gov hostnames with no embedded credentials."""
    try:
        p = urllib.parse.urlsplit(html.unescape(url).strip())
        host = (p.hostname or "").lower()
        if (p.scheme.lower() != "https" or not host.endswith(".gov")
                or host == ".gov" or p.username or p.password
                or p.port not in (None, 443)):
            return None
        cleaned = urllib.parse.urlunsplit(("https", host, p.path or "/", p.query, ""))
        return cleaned if len(cleaned) <= 1000 else None
    except ValueError:
        return None


def tenant_url(url):
    try:
        p = urllib.parse.urlsplit(html.unescape(url).strip())
        host = (p.hostname or "").lower()
        if (p.scheme.lower() != "https" or not re.fullmatch(r"[a-z0-9-]{3,40}\.legistar\.com", host, re.I)
                or p.username or p.password or p.port not in (None, 443)):
            return None
        return "https://" + host + "/"
    except ValueError:
        return None


def public_dns(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(result[4][0]).is_global for result in addresses)
    except (OSError, ValueError):
        return False


def fetch_government_page(url):
    normalized = official_url(url)
    if not normalized:
        raise ValueError("Not an official HTTPS .gov URL")
    if not public_dns(urllib.parse.urlsplit(normalized).hostname):
        raise ValueError("Government host did not resolve to a public IP")
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(normalized, headers={
        "User-Agent": USER_AGENT, "Accept": "text/html"})
    with opener.open(req, timeout=10) as response:
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Government evidence is not an HTML page")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Government evidence page exceeds size limit")
    page = GovernmentPage()
    page.feed(raw.decode("utf-8", errors="replace"))
    page.close()
    return page


def parse_label(branding):
    """Accept identity from site branding/title, never from search snippets."""
    for value in branding:
        for part in re.split(r"\s*[|–—]\s*|\s+-\s+", value):
            text = SITE_SUFFIX.sub("", " ".join(part.split())).strip()
            state = ""
            if "," in text:
                text, rest = text.split(",", 1)
                region = rest.strip().lower()
                if region.upper() in ABBREVIATIONS:
                    state = region.upper()
                elif region in STATE_CODES:
                    state = STATE_CODES[region]
                else:
                    continue
            match = OFFICIAL_NAME.search(text)
            if not match:
                continue
            name = match.group(1).strip(" .'-")
            if (4 <= len(name) <= 70 and len(name.split()) <= 8
                    and name.lower() not in ("the city", "the county", "government")):
                return name + (", " + state if state else "")
    return None


def tenant_matches_jurisdiction(tenant, label):
    """Do not attribute another city's tenant to the government linking it."""
    code = urllib.parse.urlsplit(tenant).hostname.split(".", 1)[0]
    name = re.sub(r"[^a-z0-9]", "", label.split(",", 1)[0].lower())
    return code in {name, "cityof" + name, "townof" + name,
                    "countyof" + name, name + "city", name + "county"}


def links_from_official(url, page):
    tenants, follow = set(), []
    original_host = urllib.parse.urlsplit(url).hostname
    for href, title in page.links:
        dest = urllib.parse.urljoin(url, html.unescape(href))
        tenant = tenant_url(dest)
        if tenant:
            tenants.add(tenant)
            continue
        internal = official_url(dest)
        if (internal and urllib.parse.urlsplit(internal).hostname == original_host
                and any(term in (internal + " " + title).lower() for term in FOLLOW_TERMS)
                and internal != url):
            follow.append(internal)
    return tenants, list(dict.fromkeys(follow))[:MAX_FOLLOW_PER_PAGE]


def collect():
    found = {}
    for code, label in SEEDS.items():
        item = candidate("https://" + code + ".legistar.com/", "legistar", label,
                         "verified", "https://" + code + ".legistar.com/")
        found[item["source_url"]] = item

    government_pages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tasks = {pool.submit(rss, query): query for query in QUERIES}
        for task in concurrent.futures.as_completed(tasks):
            try:
                results = task.result()
                print("Registry search results:", tasks[task], len(results))
                for link, description in results:
                    combined = html.unescape(link + " " + description)
                    for match in LEGISTAR.finditer(combined):
                        item = candidate("https://" + match.group(1) + ".legistar.com/", "legistar")
                        if item:
                            found.setdefault(item["source_url"], item)
                    url = official_url(link)
                    if url:
                        government_pages.append(url)
                    for match in GOV.finditer(combined):
                        url = official_url(match.group(0).rstrip(".,);"))
                        if url:
                            government_pages.append(url)
            except Exception as exc:
                print("Registry provider unavailable:", type(exc).__name__, str(exc)[:100])

    pending = list(dict.fromkeys(government_pages))[:MAX_SEED_PAGES]
    seen, conflicts = set(), set()
    checked = direct_links = evidence_ready = 0
    while pending and checked < MAX_GOV_PAGES:
        batch = []
        while pending and len(batch) < 6 and checked + len(batch) < MAX_GOV_PAGES:
            url = pending.pop(0)
            if url not in seen:
                seen.add(url)
                batch.append(url)
        if not batch:
            continue
        checked += len(batch)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            tasks = {pool.submit(fetch_government_page, url): url for url in batch}
            for task in concurrent.futures.as_completed(tasks):
                url = tasks[task]
                try:
                    page = task.result()
                except Exception as exc:
                    print("Government page held:", url[:130], type(exc).__name__, str(exc)[:90])
                    continue
                gov_item = candidate(url, "government_portal")
                if gov_item:
                    found.setdefault(gov_item["source_url"], gov_item)
                tenants, follow = links_from_official(url, page)
                direct_links += len(tenants)
                label = parse_label(page.branding)
                for tenant in sorted(tenants):
                    if tenant in conflicts:
                        continue
                    # Cross-jurisdiction links are not evidence that the tenant
                    # belongs to this government. Leave unknown aliases unverified.
                    matched_label = label if (label and tenant_matches_jurisdiction(tenant, label)) else None
                    item = candidate(tenant, "legistar", matched_label, "candidate",
                                     url if matched_label else None)
                    existing = found.get(tenant)
                    if existing is None:
                        found[tenant] = item
                        if matched_label:
                            evidence_ready += 1
                    elif existing["verification_status"] == "candidate" and matched_label:
                        old_label = existing.get("jurisdiction_label")
                        if old_label and old_label != matched_label:
                            conflicts.add(tenant)
                            existing["jurisdiction_label"] = None
                            existing["evidence_url"] = None
                            print("Conflicting official jurisdiction labels:", tenant)
                        elif not old_label:
                            existing["jurisdiction_label"] = matched_label
                            existing["evidence_url"] = url
                            evidence_ready += 1
                if not tenants:
                    for next_url in follow:
                        if next_url not in seen and next_url not in pending:
                            pending.append(next_url)

    print("Official government pages checked:", checked)
    print("Direct official-page Legistar links:", direct_links)
    print("Legistar candidates with government evidence:", evidence_ready)
    return found

def save(item):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": "Bearer " + key,
               "Content-Type": "application/json",
               "Prefer": "resolution=ignore-duplicates,return=minimal"}
    url = base + "/rest/v1/government_source_registry?on_conflict=source_url"
    req = urllib.request.Request(url, data=json.dumps([item]).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=12) as response:
        response.read(100)
    if (item["source_kind"] != "legistar" or item["verification_status"] != "candidate"
            or not item.get("evidence_url") or not item.get("jurisdiction_label")):
        return False
    # Only fill OLD candidate rows whose evidence AND label are both NULL.
    # Previously verified/rejected or partly reviewed rows are never changed.
    params = urllib.parse.urlencode({
        "source_url": "eq." + item["source_url"], "source_kind": "eq.legistar",
        "verification_status": "eq.candidate", "jurisdiction_label": "is.null",
        "evidence_url": "is.null", "select": "source_url"})
    patch_headers = dict(headers, Prefer="return=representation")
    patch = urllib.request.Request(base + "/rest/v1/government_source_registry?" + params,
        data=json.dumps({"jurisdiction_label": item["jurisdiction_label"],
                         "evidence_url": item["evidence_url"]}).encode(),
        method="PATCH", headers=patch_headers)
    with urllib.request.urlopen(patch, timeout=12) as response:
        body = response.read(100_001)
    if len(body) > 100_000:
        raise ValueError("Supabase patch response too large")
    rows = json.loads(body) if body else []
    return isinstance(rows, list) and bool(rows)

def main():
    found=collect()
    print("Registry sources discovered:",len(found))
    saved=0
    enriched=0
    errors=0
    for item in found.values():
        try:
            changed = save(item)
            saved+=1
            enriched+=int(changed)
        except Exception as exc:
            errors+=1
            print("Registry persistence error:",type(exc).__name__,str(exc)[:160])
            if errors>=3: raise RuntimeError("Registry persistence unavailable; apply migration 002")
    print("Registry sources submitted:",saved)
    print("Previously unknown candidates enriched:",enriched)
    print("Registry candidates are not automatically verified or published")

if __name__=="__main__": main()
