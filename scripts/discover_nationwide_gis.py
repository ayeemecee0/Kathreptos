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
    fetch_government_page, normalized_url, GIS_LINK, LINK_LABEL,
    original_disclosure_text
)
from government_domain_registry import public_dns

MAX_RESULTS=50
MAX_VISITS=28
MAX_LINKS=25
MAX_SECONDARY_VISITS=10
SECONDARY_PER_GOV_PAGE=2
GOV_MAP_LINK=re.compile(r'\b(flock|alpr|license plate|cameras?|gis|mapping)\b',re.I)
SEARCHERS=("bing-rss","ddg-html")
FLOCK=re.compile(r'\bflock\s+safety\b|\bflock\s+cameras?\b|\bflock\b.{0,35}\b(?:alpr|license[ -]plate)\b',re.I)
CAMERAS=re.compile(r'\b(camera|license plate|alpr|lpr)\b',re.I)
GIS_SERVICE=re.compile(r"/(?:MapServer|FeatureServer)/?\Z", re.I)

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
    # Use the same 10-day geographic rotation but alternate wording on
    # successive cycles. Many original government pages call these simply
    # "Flock cameras" and omit the full vendor name or an ArcGIS reference.
    state_phrase=('"Flock Safety" "camera" "map"' if (day//10)%2==0
                  else '"Flock cameras" "map"')
    queries += [(name,state_phrase+' "'+name+'" site:gov')
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
    content=original_disclosure_text(html)
    if not FLOCK.search(content) or not CAMERAS.search(content):
        return None
    found=[]
    for raw,anchor in html.anchors:
        u=normalized_url(urllib.parse.urljoin(page,raw or ""))
        if not u:continue
        path=urllib.parse.urlsplit(u).path
        direct=bool(GIS_LINK.search(path))
        service=bool(GIS_SERVICE.search(path) and
                     LINK_LABEL.search((anchor or "")+" "+path))
        # These are original direct anchors, not searches or adjacent site
        # links. Service roots are explicitly PRIVATE until the source
        # verifier resolves a uniquely identified Flock camera layer.
        candidate=u.rstrip("/")
        if (direct or service) and candidate not in found:
            found.append(candidate)
            if len(found)>=MAX_LINKS:break
    excerpt=" ".join(content.split())[:580]
    return {
      "page_url":page,"state_search_hint":label,"discovery_query":query,
      "page_sha256":hash_value,
      "gis_links":found,
      "evidence_excerpt":excerpt if len(excerpt)>=12 else
          "Original government page explicitly mentions Flock Safety camera deployment.",
    }


def direct_same_host_flock_pages(document,page):
    """At most two same-host navigation leads from a sourced Flock page.

    This is original-government discovery, NOT government camera approval.
    A subpage will be accepted only if its OWN live HTML mentions Flock
    AND a camera program AND directly links an original GIS service/layer.
    """
    choices=[]
    base=urllib.parse.urlsplit(page)
    for raw,label in document.anchors:
        if not isinstance(raw,str) or not isinstance(label,str) or not GOV_MAP_LINK.search(label):
            continue
        candidate=gov_url(urllib.parse.urljoin(page,raw))
        if not candidate:
            continue
        p=urllib.parse.urlsplit(candidate)
        if (p.hostname!=base.hostname or p.port not in (None,443)
            or candidate==page or candidate in choices):
            continue
        if GIS_LINK.search(p.path) or GIS_SERVICE.search(p.path):
            continue
        choices.append(candidate)
        if len(choices)>=SECONDARY_PER_GOV_PAGE:
            break
    return choices


def stage(item):
    """Insert or recheck a live original .gov page and its GIS anchor list.

    Previously discovered pages are not frozen in time. Link changes are
    appended to the private original-page evidence ledger via a restricted
    backend RPC, never promoted to camera source approval.
    """
    lookup="government_gis_search_queue?"+urllib.parse.urlencode({
      "select":"page_sha256,gis_links",
      "page_url":"eq."+item["page_url"],"limit":"2"})
    prior=api_request(lookup)
    if not isinstance(prior,list) or len(prior)>1:
        raise ValueError("Government discovery page identity ambiguous")
    if prior:
        digest=prior[0].get("page_sha256")
        if not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest):
            raise ValueError("Original government page hash malformed")
        receipt=api_request("rpc/refresh_original_government_gis_search_lead",
          method="POST",payload={
            "p_page_url":item["page_url"],
            "p_expected_previous_sha":digest,
            "p_current_page_sha":item["page_sha256"],
            "p_gis_links":item["gis_links"]
          })
        if receipt is not True:
            raise ValueError("Original government page GIS evidence refresh refused")
        return
    receipt=api_request("government_gis_search_queue?on_conflict=page_url",
      method="POST",payload=[item],
      prefer="resolution=ignore-duplicates,return=minimal")
    if receipt is not None:
        raise ValueError("Unexpected unverified government discovery queue response")


def upstream_government_source_seeds():
    """Reuse new original .gov sources found by the existing nationwide discoverer.

    Original source links are still unverified until the fetched page itself
    clearly documents a Flock camera program; no community claim is trusted.
    """
    # The nationwide news backlog can exceed the 50-KB Supabase API
    # response limit. Query only .gov-looking URLs and page in bounded
    # batches; the original URL still undergoes strict hostname validation.
    prior=[]
    for offset in range(0,900,25):
        batch=api_request("discovery_queue?select=url,state_hint"
                          "&url=like.*.gov/*&order=url.asc&limit=25&offset="
                          +str(offset))
        if not isinstance(batch,list) or len(batch)>25:
            raise ValueError("Existing original-government discovery page malformed")
        prior.extend(batch)
        if len(batch)<25:
            break
    else:
        raise ValueError("Existing government discovery source search truncated")
    agendas=api_request("verified_flock_agenda_mentions?select=government_evidence_url&"
                       "status=eq.verified&limit=100")
    programs=api_request("flock_documented_programs?select=official_evidence_url,state_code"
                         "&record_status=eq.verified&limit=100")
    if (not isinstance(agendas,list) or len(agendas)>=100
        or not isinstance(programs,list) or len(programs)>=100):
        raise ValueError("Verified public government source registry truncated")
    found={}
    for item in prior:
        url=gov_url(item.get("url") or "")
        if url:
            found[url]=(str(item.get("state_hint") or "Government discovery")[:90],
                        "Flock Safety original government discovery queue")
    for item in agendas:
        url=gov_url(item.get("government_evidence_url") or "")
        if url:
            found[url]=("Verified legislative record","Flock Safety legislative government source")
    for item in programs:
        url=gov_url(item.get("official_evidence_url") or "")
        if url:
            found[url]=(str(item.get("state_code") or "Official program"),
                        "Original government Flock program citation")
    return found


def prioritize_new_government_pages(hits,already_staged,day=None):
    """Rotate the discovery queue rather than reopening only first search hits.

    Unstaged original .gov URLs are visited first, and then older staged pages
    are rechecked to detect new links. Every candidate still requires a live
    original-government page fetch and separate Flock evidence checks.
    """
    day=day or dt.datetime.now(dt.timezone.utc).date()
    if not isinstance(already_staged,set):
        raise ValueError("Existing source registry must be a complete set")
    def order(item):
        url=item[0]
        bucket=(url in already_staged)
        # Daily deterministic hash diversifies page samples even if a search
        # provider always returns sources in exactly the same order.
        digest=hashlib.sha256((day.isoformat()+"|"+url).encode()).hexdigest()
        return (bucket,digest)
    return sorted(hits.items(),key=order)


def previously_checked_original_pages():
    from paged_supabase import fetch_all
    rows=fetch_all(api_request,
      "government_gis_search_queue?select=page_url","page_url")
    if not all(isinstance(x,dict) and isinstance(x.get("page_url"),str) for x in rows):
        raise ValueError("Previously discovered government page registry malformed")
    return {x["page_url"] for x in rows}


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
    try:
        seed_urls=upstream_government_source_seeds()
        counts["source_registry_gov_urls"]=len(seed_urls)
        for url,hint in seed_urls.items():
            hits.setdefault(url,hint)
    except Exception as exc:
        counts["registry_errors"]+=1
        print("Existing original-government discovery source registry held:",
              type(exc).__name__,str(exc)[:120])
    if not counts["searches_completed"] and not hits:
        raise ValueError("All national source search and original-government registries unavailable")
    counts["gov_search_urls"]=len(hits)
    try:
        observed=previously_checked_original_pages()
    except Exception as exc:
        counts["registry_errors"]+=1
        raise RuntimeError("Cannot select unvisited government URLs without full source registry") from exc
    counts["gov_sources_previously_staged"]=len(observed)
    checked_hosts=set()
    secondary_visited=set()
    for url,(label,query) in prioritize_new_government_pages(hits,observed)[:MAX_VISITS]:
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
                # Government Flock disclosure pages often link a dedicated
                # city GIS page instead of the ArcGIS endpoint itself.
                # Bounded one-hop discovery gives the exact GIS subpage an
                # independent HTML fingerprint; never inherit a parent-page
                # Flock claim as camera or owner authority.
                for sub in direct_same_host_flock_pages(html,url):
                    if (len(secondary_visited)>=MAX_SECONDARY_VISITS or
                        sub in secondary_visited or sub in observed):
                        continue
                    secondary_visited.add(sub)
                    try:
                        sub_html,sub_sha=fetch_government_page(sub)
                        counts["secondary_pages_checked"]+=1
                        sub_item=page_candidate(
                            sub,label,"Same-host original .gov Flock disclosure",sub_html,sub_sha)
                        if not sub_item or not sub_item["gis_links"]:
                            continue
                        counts["secondary_pages_with_direct_gis"]+=1
                        counts["direct_gis_links"]+=len(sub_item["gis_links"])
                        if not dry_run:
                            stage(sub_item);counts["submitted"]+=1
                    except Exception as secondary_error:
                        counts["secondary_pages_held"]+=1
                        print("Original government Flock subpage held:",
                              urllib.parse.urlsplit(sub).hostname,
                              type(secondary_error).__name__,str(secondary_error)[:100])
        except Exception as exc:
            counts["pages_held"]+=1
            print("Original .gov page inaccessible:",host,type(exc).__name__,str(exc)[:100])
    for k in ("searches_completed","search_errors","source_registry_gov_urls","registry_errors",
              "gov_search_urls","gov_sources_previously_staged","pages_checked",
              "flock_pages","direct_gis_links","submitted","pages_held",
              "secondary_pages_checked","secondary_pages_with_direct_gis",
              "secondary_pages_held","unsafe_hosts"):
        print("National GIS candidate",k+":",counts[k])
    print("Newly approved government GIS authorities from search: 0")
    print("Camera coordinates published from search hits: 0")
    return counts


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    result=scan(a.parse_args().dry_run)
    if result["searches_completed"]==0 and result["source_registry_gov_urls"]==0:
        raise SystemExit("No functioning government GIS discovery source")
