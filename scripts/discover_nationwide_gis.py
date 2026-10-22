"""National government GIS discovery from government-original pages (private only).

Rotate all 50 states over ten daily runs. Search engines are DISCOVERY hints,
not independent authority. A page qualifies as a lead only after fetching
its original public .gov HTML and finding a Flock-specific camera reference.
Direct official GIS links are preserved as candidate evidence, never published
as camera locations or independently verified government GIS authority.
"""
import argparse
import datetime as dt
import hashlib
import re
import urllib.parse
from collections import Counter

from auto_verify_flock_agenda import api_request
from discover_official import STATES, normalize_url, is_gov, search_provider
from discover_government_gis_links import (
    fetch_government_page, gis_candidate_links, normalized_url, GIS_LINK
)
from government_domain_registry import public_dns

MAX_RESULTS=50
MAX_VISITS=28
MAX_LINKS=25
SEARCHERS=("bing-rss","ddg-html")
FLOCK=re.compile(r'\bflock\s+safety\b|\bflock\b.{0,35}\balpr\b',re.I)
CAMERAS=re.compile(r'\b(camera|license plate|alpr|lpr)\b',re.I)


def query_plan(today=None):
    day=(today or dt.datetime.now(dt.timezone.utc)).timetuple().tm_yday
    items=list(STATES)
    group=day%10
    states=items[group::10]
    queries=[
      ('National','"Flock Safety" "GIS" "camera" site:gov'),
      ('National','"Flock cameras" "MapServer" site:gov'),
      ('National','"Flock Safety" "camera map" site:gov'),
    ]
    queries += [(name,'"Flock Safety" "camera" "map" "'+name+'" site:gov')
                for name in states]
    return queries


def gov_url(item):
    value=normalize_url(item)
    if not value or not is_gov(value):return None
    p=urllib.parse.urlsplit(value)
    if p.port not in (None,443) or p.username or p.password:return None
    # Search hits containing a fragment/query can still be inspected, but do
    # not fetch arbitrary search-engine redirects or non-public destinations.
    return normalized_url(value)


def page_candidate(page,label,query,html,hash_value):
    content=" ".join(html.text)
    if not FLOCK.search(content) or not CAMERAS.search(content):
        return None
    found=[]
    for raw,anchor in html.anchors:
        u=normalized_url(urllib.parse.urljoin(page,raw or ""))
        if u and GIS_LINK.search(urllib.parse.urlsplit(u).path) and u not in found:
            found.append(u)
            if len(found)>=MAX_LINKS:break
    excerpt=" ".join(content.split())[:580]
    return {
      "page_url":page,"state_search_hint":label,"discovery_query":query,
      "page_sha256":hash_value,
      "gis_links":found,
      "evidence_excerpt":excerpt if len(excerpt)>=12 else
          "Original government page explicitly mentions Flock Safety camera deployment.",
    }


def stage(item):
    receipt=api_request("government_gis_search_queue?on_conflict=page_url",
      method="POST",payload=[item],
      prefer="resolution=ignore-duplicates,return=minimal")
    if receipt is not None:
        raise ValueError("Unexpected unverified government discovery queue response")


def scan(dry_run=False,plan=None):
    counts=Counter();hits={}
    for label,query in (plan or query_plan()):
        for provider in SEARCHERS:
            url=(("https://www.bing.com/search?format=rss&q=" if provider=="bing-rss"
                  else "https://html.duckduckgo.com/html/?q=")+urllib.parse.quote(query))
            try:
                _,result=search_provider((provider,url))
                if not isinstance(result,list):
                    raise ValueError("Search provider did not return parseable links")
                counts["searches_completed"]+=1
                for raw in result[:MAX_RESULTS]:
                    original=gov_url(raw)
                    if original and original not in hits:
                        hits[original]=(label,query)
            except Exception as exc:
                counts["search_errors"]+=1
                print("National GIS discovery search held:",label,provider,
                      type(exc).__name__,str(exc)[:120])
    if not counts["searches_completed"]:
        raise ValueError("All national government source discovery providers unavailable")
    counts["gov_search_urls"]=len(hits)
    checked_hosts=set()
    for url,(label,query) in list(hits.items())[:MAX_VISITS]:
        host=urllib.parse.urlsplit(url).hostname
        # Avoid private/internal resolved IPs and DNS rebinding as far as the
        # stdlib's pre-request checks allow. Never reuse unapproved redirects.
        if host not in checked_hosts and not public_dns(host):
            counts["unsafe_hosts"]+=1;continue
        checked_hosts.add(host)
        try:
            html,sha=fetch_government_page(url)
            counts["pages_checked"]+=1
            item=page_candidate(url,label,query,html,sha)
            if item:
                counts["flock_pages"]+=1
                counts["direct_gis_links"]+=len(item["gis_links"])
                if not dry_run:
                    stage(item);counts["submitted"]+=1
        except Exception as exc:
            counts["pages_held"]+=1
            print("Original .gov page inaccessible:",host,type(exc).__name__,str(exc)[:100])
    for k in ("searches_completed","search_errors","gov_search_urls","pages_checked",
              "flock_pages","direct_gis_links","submitted","pages_held","unsafe_hosts"):
        print("National GIS candidate",k+":",counts[k])
    print("Newly approved government GIS authorities from search: 0")
    print("Camera coordinates published from search hits: 0")
    return counts


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    result=scan(a.parse_args().dry_run)
    if result["searches_completed"]==0:
        raise SystemExit("No functioning official GIS discovery search provider")
