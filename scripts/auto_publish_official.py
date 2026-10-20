"""Conservative official-source auto-publication: program documentation only.

No camera counts, contract terms, individual activity, or inferred votes.
Only pinned agency pages are eligible. RSS discoveries remain review-only.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SOURCES = [
    dict(state="IL", city="Wilmette", agency="Wilmette Police Department",
         url="https://www.wilmette.gov/295/Automated-License-Plate-Readers-ALPR",
         publisher="Village of Wilmette", marker="Wilmette",
         description="The Village of Wilmette publishes information about its Flock Safety automated license plate reader program."),
    dict(state="MN", city="Shakopee", agency="Shakopee Police Department",
         url="https://www.shakopeemn.gov/public_safety/police_department/reports___transparency.php",
         publisher="City of Shakopee", marker="Shakopee",
         description="The City of Shakopee publishes information about its Flock Safety automated license plate reader program."),
    dict(state="MA", city="Taunton", agency="Taunton Police Department",
         url="https://tauntonpd.com/alpr-transparency-portal/",
         publisher="Taunton Police Department", marker="Taunton",
         description="The Taunton Police Department publishes information about its Flock Safety automated license plate reader program."),
]

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Katoptron-public-records/1.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        final = urllib.parse.urlsplit(res.url)
        expected = urllib.parse.urlsplit(url)
        if final.scheme != "https" or final.hostname != expected.hostname:
            raise ValueError("Redirect outside pinned official host")
        if "text/html" not in res.headers.get("Content-Type", ""):
            raise ValueError("Unexpected content type")
        body = res.read(600_001)
        if len(body) > 600_000: raise ValueError("Page too large")
    parser = TextExtractor()
    parser.feed(body.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parser.parts))

def eligible(text, row):
    # Require clear, same-page references; never infer contract amounts or deployment.
    return (row["marker"].lower() in text.lower()
            and re.search(r"\bflock\s+safety\b", text, re.I)
            and re.search(r"\b(ALPR|automatic license plate reader|automated license plate reader)\b", text, re.I))

def api(method, table, key, url, payload=None, query=""):
    endpoint = url.rstrip("/") + "/rest/v1/" + table + query
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
    if data is not None:
        headers.update({"Content-Type": "application/json", "Prefer": "return=representation"})
    req = urllib.request.Request(endpoint, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=25) as res:
        body = res.read()
        return json.loads(body) if body else []

def eq(field, value):
    return field + "=eq." + urllib.parse.quote(str(value), safe="")

def get_one(table, filters, key, url):
    result = api("GET", table, key, url, query="?" + "&".join(filters) + "&limit=1")
    return result[0] if result else None

def get_or_create(table, filters, values, key, url):
    existing = get_one(table, filters, key, url)
    if existing: return existing
    return api("POST", table, key, url, [values])[0]

def publish(row, key, url):
    j = get_or_create("jurisdictions", [eq("state_code", row["state"]), eq("name", row["city"]), eq("kind", "city")],
                      {"state_code": row["state"], "name": row["city"], "kind": "city"}, key, url)
    a = get_or_create("agencies", [eq("jurisdiction_id", j["id"]), eq("name", row["agency"])],
                      {"jurisdiction_id": j["id"], "name": row["agency"], "official_url": row["url"]}, key, url)
    s = get_one("sources", [eq("url", row["url"])], key, url)
    if s and s["status"] == "rejected":
        print("Skipping rejected source:", row["url"])
        return
    if not s:
        s = api("POST", "sources", key, url, [{"url": row["url"], "title": row["agency"] + " ALPR program",
               "publisher": row["publisher"], "source_type": "official_agency", "status": "verified"}])[0]
    elif s["status"] != "verified":
        s = api("PATCH", "sources", key, url, {"status": "verified"},
                query="?" + eq("id", s["id"]))[0]
    existing = get_one("actions", [eq("agency_id", a["id"]), eq("source_id", s["id"]),
                                   eq("factual_description", row["description"])], key, url)
    if existing: return
    api("POST", "actions", key, url, [{"agency_id": a["id"], "jurisdiction_id": j["id"],
        "action_type": "other", "factual_description": row["description"],
        "recorded_position": "not_applicable", "source_id": s["id"], "review_status": "published"}])
    print("Published:", row["agency"])

def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    for row in SOURCES:
        try:
            text = fetch_text(row["url"])
            if eligible(text, row):
                publish(row, key, url)
            else:
                print("Held for review: evidence insufficient:", row["url"])
        except Exception as exc:
            print("Held for review:", row["url"], type(exc).__name__, str(exc)[:180])

if __name__ == "__main__":
    main()
