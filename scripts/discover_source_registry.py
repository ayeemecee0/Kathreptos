"""Discover government portals and persist candidates in a private Supabase registry.

Search-result mentions are NEVER sufficient to verify jurisdiction or publish records.
Only preapproved Legistar tenants are verified automatically. All other entries are
candidates requiring explicit source-to-jurisdiction verification.
"""
import concurrent.futures
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SEEDS = {"costamesa":"Costa Mesa, CA","oakland":"Oakland, CA",
         "seattle":"Seattle, WA","lacounty":"Los Angeles County, CA"}
QUERIES = [
    '"Flock Safety" "legistar.com"',
    '"license plate reader" "legistar.com"',
    '"Flock Safety" "city council" "legistar"',
    '"Flock Safety" "agenda" site:gov',
    '"automated license plate reader" "procurement" site:gov',
    '"Flock Safety" "transparency" site:gov',
]
LEGISTAR = re.compile(r"https?://([a-z0-9-]{3,40})\\.legistar\\.com(?:/|\\b)",re.I)
GOV = re.compile(r"https?://[a-z0-9.-]+\\.gov(?:/[^\\s<>\"']*)?",re.I)

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
    if kind=="legistar" and not re.fullmatch(r"[a-z0-9-]{3,40}\\.legistar\\.com",host):
        return None
    if kind!="legistar" and not host.endswith(".gov"):
        return None
    normalized="https://"+host+(p.path or "/")
    return {"source_url":normalized[:1000],"host":host,"source_kind":kind,
            "jurisdiction_label":label,"verification_status":status,
            "evidence_url":evidence}

def collect():
    found={}
    for code,label in SEEDS.items():
        item=candidate("https://"+code+".legistar.com/","legistar",label,"verified",
                       "https://"+code+".legistar.com/")
        found[item["source_url"]]=item
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(rss,q):q for q in QUERIES}
        for future in concurrent.futures.as_completed(futures):
            try:
                items=future.result()
                print("Registry search results:",futures[future],len(items))
                for link,description in items:
                    # Only explicit URLs in the returned links/snippets; never
                    # treat a news result itself as an official source.
                    for match in LEGISTAR.finditer(link+" "+description):
                        code=match.group(1).lower()
                        item=candidate("https://"+code+".legistar.com/","legistar")
                        if item: found.setdefault(item["source_url"],item)
                    for match in GOV.finditer(link+" "+description):
                        item=candidate(match.group(0),"government_portal")
                        if item: found.setdefault(item["source_url"],item)
            except Exception as exc:
                print("Registry provider unavailable:",type(exc).__name__,str(exc)[:100])
    return found

def save(item):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    # Ignore duplicates to preserve prior review decisions.
    url=base+"/rest/v1/government_source_registry?on_conflict=source_url"
    req=urllib.request.Request(url,data=json.dumps([item]).encode(),method="POST",
      headers={"apikey":key,"Authorization":"Bearer "+key,"Content-Type":"application/json",
               "Prefer":"resolution=ignore-duplicates,return=minimal"})
    with urllib.request.urlopen(req,timeout=12) as response: return response.status

def main():
    found=collect()
    print("Registry sources discovered:",len(found))
    saved=0
    errors=0
    for item in found.values():
        try:
            save(item)
            saved+=1
        except Exception as exc:
            errors+=1
            print("Registry persistence error:",type(exc).__name__,str(exc)[:160])
            if errors>=3: raise RuntimeError("Registry persistence unavailable; apply migration 002")
    print("Registry sources submitted:",saved)
    print("Registry candidates are not automatically verified or published")

if __name__=="__main__": main()
