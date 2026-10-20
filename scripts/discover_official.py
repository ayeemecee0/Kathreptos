"""Discover and auto-publish only strongly matched official municipal .gov ALPR pages.

Fail closed on ambiguous jurisdiction, redirects, missing evidence, or third-party domains.
The record only asserts that the municipal website publishes Flock ALPR information.
"""
import re
import urllib.parse
import urllib.request
import feedparser
import json
from html.parser import HTMLParser
from pathlib import Path
from auto_publish_official import fetch_text, publish

STATES = {
"Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
"Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
"Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
"Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
"Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO",
"Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ",
"New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND",
"Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI",
"South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT",
"Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV",
"Wisconsin":"WI","Wyoming":"WY"
}
QUERIES = [
 'site:.gov "Flock Safety" "license plate" "City of"',
 'site:.gov "Flock Safety" "ALPR" "City of"',
 'site:.gov "Flock Safety" "police" "City of"',
]
class ResultLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag != "a": return
        d = dict(attrs)
        if d.get("href"): self.links.append(d["href"])

def official_url(raw):
    try:
        parsed = urllib.parse.urlsplit(raw)
        if parsed.path == "/url" and parsed.hostname in ("www.google.com", "google.com"):
            raw = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            parsed = urllib.parse.urlsplit(raw)
        if parsed.scheme != "https" or parsed.username or parsed.password: return None
        host = (parsed.hostname or "").lower().rstrip(".")
        if not (host == "gov" or host.endswith(".gov")): return None
        if host == "gov": return None
        if any(x in parsed.path.lower() for x in ("/login", "/signin")): return None
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    except ValueError: return None

def candidates():
    links = set()
    diagnostics = []
    # Two independent search formats. Search pages may rate-limit automated clients;
    # never treat an empty response as evidence that no official records exist.
    for q in QUERIES:
        for provider, url in [
            ("bing-rss", "https://www.bing.com/search?format=rss&q="+urllib.parse.quote(q)),
            ("google-html", "https://www.google.com/search?q="+urllib.parse.quote(q)+"&num=30"),
            ("ddg-html", "https://www.google.com/search?q="+urllib.parse.quote(q)+"&num=20"),
        ]:
            try:
                req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; Katoptron/1.0)"})
                with urllib.request.urlopen(req, timeout=12) as res:
                    body = res.read(450000).decode("utf-8", "replace")
                raw_links = []
                if provider == "bing-rss":
                    raw_links = [item.get("link","") for item in feedparser.parse(body).entries]
                else:
                    parser = ResultLinks()
                    parser.feed(body)
                    raw_links = parser.links
                before = len(links)
                for raw in raw_links:
                    candidate = official_url(raw)
                    if candidate: links.add(candidate)
                diagnostics.append((provider, len(raw_links), len(links)-before))
            except Exception as exc:
                diagnostics.append((provider, "error", type(exc).__name__))
    # The news discovery stage supplies additional leads. These are ONLY eligible
    # if their URLs themselves are direct official government URLs.
    path = Path("candidates.json")
    if path.is_file():
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            candidate = official_url(row.get("url",""))
            if candidate: links.add(candidate)
    print("Search diagnostics:", diagnostics)
    return sorted(links)[:60]

def identify(url,text):
    host=(urllib.parse.urlsplit(url).hostname or "").lower()
    if not host.endswith(".gov"): return None
    # Must explicitly identify the city's government and its state, not just mention a city.
    # City name must also be represented in the government hostname.
    header=text[:1600]
    matches=re.findall(r"\bCity of ([A-Z][A-Za-z]+(?:[ -][A-Z][A-Za-z]+){0,2})\b",header)
    if not matches: return None
    found_states=[(name,code) for name,code in STATES.items() if re.search(r"\b"+re.escape(name)+r"\b",header,re.I)]
    if len(found_states)!=1: return None
    city=matches[0].strip()
    token=re.sub(r"[^a-z]","",city.lower())
    hostparts=re.sub(r"[^a-z]","",host.split(".gov")[0])
    if len(token)<4 or token not in hostparts: return None
    if not re.search(r"\bFlock\s+Safety\b",text,re.I): return None
    if not re.search(r"\b(ALPR|automated license plate reader|automatic license plate reader)s?\b",text,re.I): return None
    return dict(state=found_states[0][1],city=city,agency="City of "+city,
                url=url,publisher="City of "+city,marker=city,
                description="The official City of "+city+" website publishes information about Flock Safety automated license plate readers.")

def main():
    import os
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    base=os.environ["SUPABASE_URL"]
    links=candidates()
    print("Official .gov candidates:",len(links))
    published=0
    for link in links:
        try:
            text=fetch_text(link)
            row=identify(link,text)
            if row:
                publish(row,key,base)
                published+=1
            else: print("Review required (insufficient identity/evidence):",link)
        except Exception as exc:
            print("Review required:",link,type(exc).__name__,str(exc)[:100])
    print("Eligible official pages processed:",published)

if __name__=="__main__":
    main()
