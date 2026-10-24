"""Search ORIGINAL .gov web pages for exact links to external ArcGIS publishers.

This increases the independent original-agency discovery surface beyond the
fixed government pages already monitored by probe_original_gov_arcgis_org_links.
Search-engine URLs are hints only: NEVER evidence themselves. Original .gov
HTML must link to the exact Esri organization (orgId or verified map portal).
Result is an unapproved PRIVATE research lead, not a source registration,
camera location, government endorsement or operational-camera claim.

Rotates a small slice of the seven private Esri candidates; consumes only
free public Bing RSS search and original government HTML. No Supabase writes.
"""
from collections import Counter
from urllib.parse import quote, urlsplit
import datetime as dt
import hashlib
import re

from audit_external_arcgis_candidates import (
    candidate_inputs, inspect_arcgis_publisher, LAYER_URL
)
from discover_official import search_provider, normalize_url, is_gov
from discover_government_gis_links import fetch_government_page
from probe_original_gov_arcgis_org_links import linked_government_org

PER_RUN=3
MAX_RESULTS_PER_SEARCH=12
MAX_GOV_FETCHES_PER_RUN=24
ORG=re.compile(r'^[A-Za-z0-9]{8,48}$')
PORTAL=re.compile(r'^[A-Za-z0-9-]{3,90}$')
FLOCK=re.compile(r'\bflock\b',re.I)
GOV_CAMERA=re.compile(r'\b(camera|license plate|alpr|lpr)\b',re.I)

def pick(candidates,day=None):
    """Stable rotating partitions cover all sources without a large crawler."""
    rows=sorted(candidates,key=lambda x:x['gis_layer_url'])
    if len(rows)>36:
        raise ValueError('External ArcGIS source backlog exceeded discovery budget')
    if not rows:
        return []
    today=(day if day is not None else dt.datetime.now(dt.timezone.utc).date().toordinal())
    offset=(today*PER_RUN)%len(rows)
    return [rows[(offset+i)%len(rows)] for i in range(min(PER_RUN,len(rows)))]

def queries_for_identity(identity):
    """Exact original IDs and portal addresses; no self-reported city title."""
    if not isinstance(identity,dict) or not ORG.fullmatch(identity.get('org_id') or ''):
        return []
    urls=[('site:.gov "orgId='+identity['org_id']+'"')]
    portal=identity.get('portal_url_key')
    base=identity.get('portal_base_url')
    if base=='maps.arcgis.com' and isinstance(portal,str) and PORTAL.fullmatch(portal):
        urls.append('site:.gov "'+portal.lower()+'.maps.arcgis.com"')
    return urls[:2]

def bing_rss(query,search=search_provider):
    # Search results are never a government-authority proof.
    endpoint='https://www.bing.com/search?format=rss&q='+quote(query)
    provider,found=search(('bing-rss',endpoint))
    if provider!='bing-rss' or not isinstance(found,list):
        raise ValueError('Search results unavailable or untrusted')
    return found[:MAX_RESULTS_PER_SEARCH]

def gov_pages(queries,search=search_provider):
    """Return only strict HTTPS government URLs, de-duplicated, no redirects."""
    result=[]
    for query in queries:
        for raw in bing_rss(query,search):
            url=normalize_url(raw)
            if (not url or not is_gov(url) or urlsplit(url).fragment
                    or urlsplit(url).query or len(url)>1200):
                continue
            if url not in result:
                result.append(url)
            if len(result)>=MAX_GOV_FETCHES_PER_RUN:
                return result
    return result

def evaluate_page(original,identity,page,document):
    """Government article with exact Esri portal link is a *lead*, not trust."""
    if not linked_government_org(document,page,identity):
        return 'no_exact_government_to_publisher_link'
    content=' '.join(document.text)[:500000]
    # A generic GIS portal link on a county GIS page is government publisher
    # association evidence, NOT independent confirmation of Flock ALPR.
    if FLOCK.search(content) and GOV_CAMERA.search(content):
        return 'agency_page_links_exact_esri_org_and_mentions_flock'
    return 'agency_page_links_exact_esri_org_only_no_flock_evidence'

def run(search=search_provider,fetch_page=fetch_government_page,day=None):
    candidates,_,trusted=candidate_inputs()
    trusted_urls={x['gis_layer_url'] for x in trusted}
    external=[r for r in candidates
              if LAYER_URL.fullmatch(r.get('gis_layer_url') or '')
              and r.get('gis_layer_url') not in trusted_urls]
    results=Counter()
    seen_pages={}
    for row in pick(external,day):
        url=row['gis_layer_url']
        marker=hashlib.sha256(url.encode()).hexdigest()[:12]
        try:
            identity=inspect_arcgis_publisher(url,return_identity=True)
            if not isinstance(identity,dict):
                results['exact_arcgis_publisher_unavailable']+=1
                continue
            queries=queries_for_identity(identity)
            if not queries:
                results['exact_esri_org_identity_unavailable']+=1
                continue
            results['independent_esri_org_identified']+=1
            pages=gov_pages(queries,search)
            results['government_search_results']+=len(pages)
            for page in pages:
                try:
                    if page not in seen_pages:
                        seen_pages[page]=fetch_page(page)
                    document,digest=seen_pages[page]
                    outcome=evaluate_page(row,identity,page,document)
                    results[outcome]+=1
                    if outcome.startswith('agency_page_links_exact_esri_org'):
                        # No unpublished URLs, publisher IDs, geometry or
                        # coordinates are printed in a public Actions log.
                        page_hash=hashlib.sha256(page.encode()).hexdigest()[:12]
                        print('ORIGINAL AGENCY PUBLISHER LINK LEAD',marker,
                              'gov_page_sha',page_hash,'classification',outcome)
                except Exception as exc:
                    results['government_original_page_unavailable']+=1
                    print('ORIGINAL AGENCY PUBLISHER SEARCH HELD',marker,
                          type(exc).__name__)
        except Exception as exc:
            results['source_investigation_unavailable']+=1
            print('ORIGINAL AGENCY PUBLISHER SOURCE HELD',marker,type(exc).__name__)
    for name in sorted(results):
        print('TARGETED ESRI ORIGINAL-GOV RESEARCH',name,results[name])
    print('EXTERNAL ARC GIS SOURCES AUTOMATICALLY VERIFIED 0')
    print('CAMERAS AUTOMATICALLY PUBLISHED 0')
    return results

if __name__=='__main__':
    run()
