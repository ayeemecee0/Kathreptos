
def safe_official_url(url):
    """Avoid requesting arbitrary hosts or credentials supplied by registry rows."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        return False
    if not parts.hostname or not official_host(parts.hostname):
        return False
    # Reject resolved private/loopback destinations; recheck after DNS resolution.
    try:
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, ValueError):
        return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Evidence page redirects; manual verification required")


def fetch_official_html(url):
    if not safe_official_url(url):
        raise ValueError("Evidence URL is not an approved public HTTPS .gov address")
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": BASE_HEADERS["User-Agent"],
                                               "Accept": "text/html"})
    with opener.open(req, timeout=12) as response:
        ctype = response.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype:
            raise ValueError("Evidence is not HTML")
        raw = response.read(500_001)
    if len(raw) > 500_000:
        raise ValueError("Evidence page too large")
    return raw.decode("utf-8", errors="replace")


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


def verify(row):
    source_url = str(row.get("source_url") or "")
    evidence_url = str(row.get("evidence_url") or "")
    label = str(row.get("jurisdiction_label") or "").strip()
    tenant = valid_tenant_url(source_url)
    if not tenant or not evidence_url or not label or label.lower().startswith("legistar tenant"):
        return False, "missing or invalid tenant, evidence URL, or jurisdiction label"
    if not safe_official_url(evidence_url):
        return False, "evidence URL is not a valid public .gov page"
    document = LinkParser()
    document.feed(fetch_official_html(evidence_url))
    evidence_host = urllib.parse.urlsplit(evidence_url).hostname or ""
    matched = False
    for href in document.links:
        target = urllib.parse.urljoin(evidence_url, href)
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
    return True, "official .gov page links to tenant and identifies jurisdiction"


def main():
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
            ok, reason = verify(row)
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
