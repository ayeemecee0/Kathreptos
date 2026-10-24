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
from urllib.parse import quote, urlsplit, parse_qs, urljoin, urlencode
import datetime as dt
import hashlib
import re

from audit_external_arcgis_candidates import (
    candidate_inputs, inspect_arcgis_publisher, LAYER_URL
)
from auto_verify_camera_gis import get_official_json
from discover_official import search_provider, normalize_url, is_gov
from discover_government_gis_links import fetch_government_page
from probe_original_gov_arcgis_org_links import linked_government_org

PER_RUN=3
MAX_RESULTS_PER_SEARCH=12
MAX_GOV_FETCHES_PER_RUN=24
ORG=re.compile(r'^[A-Za-z0-9]{8,48}$')
ITEM_ID=re.compile(r'^[a-fA-F0-9]{32}$')
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

def inspect_original_service_item(layer_url,owner,fetch=None):
    """Independently fetch original Esri *item*, not user-supplied title metadata."""
    fetch=fetch or get_official_json
    if (not isinstance(layer_url,str) or not LAYER_URL.fullmatch(layer_url)
        or not isinstance(owner,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,90}',owner)):
        return None
    service=layer_url.rsplit('/',1)[0]
    query=urlencode({'f':'json','q':'type:"Feature Service" AND url:"'+service+'"','num':30})
    listing=fetch('https://www.arcgis.com/sharing/rest/search?'+query)
    rows=listing.get('results') if isinstance(listing,dict) else None
    if not isinstance(rows,list) or len(rows)>30:return None
    matches=[row for row in rows if isinstance(row,dict) and
        row.get('type')=='Feature Service' and row.get('url')==service and
        row.get('owner')==owner and isinstance(row.get('id'),str) and
        ITEM_ID.fullmatch(row['id'])]
    if len(matches)!=1:return None
    item_id=matches[0]['id']
    original=fetch('https://www.arcgis.com/sharing/rest/content/items/'+item_id+'?f=json')
    if (not isinstance(original,dict) or original.get('id')!=item_id or
        original.get('type')!='Feature Service' or
        original.get('url')!=service or original.get('owner')!=owner):
        return None
    return item_id.lower()

def linked_original_esri_service_item(document,page,identity):
    """Accept only the exact audited Feature Service item via original gov anchor."""
    item=identity.get('original_service_item_id') if isinstance(identity,dict) else None
    if not isinstance(item,str) or not ITEM_ID.fullmatch(item):
        return False
    for href,label in document.anchors:
        if not isinstance(href,str) or len(href)>1500:continue
        try:
            u=urlsplit(urljoin(page,href))
            if (u.scheme!='https' or u.username or u.password or u.port not in (None,443)
                or u.fragment or u.path.lower()!='/home/item.html'):
                continue
            if u.hostname not in ('www.arcgis.com','arcgis.com'):
                # A branded Esri portal is acceptable only when its domain
                # *independently* matches the confirmed publisher portal.
                key=identity.get('portal_url_key')
                if (identity.get('portal_base_url')!='maps.arcgis.com' or
                    not isinstance(key,str) or not PORTAL.fullmatch(key) or
                    u.hostname!=key.lower()+'.maps.arcgis.com'):
                    continue
            params=parse_qs(u.query,keep_blank_values=True)
            if len(params)!=1 or len(params.get('id',[]))!=1:
                continue
            if params['id'][0].lower()==item:
                return True
        except ValueError:
            continue
    return False

def queries_for_identity(identity):
    """Exact original IDs and portal addresses; no self-reported city title."""
    if not isinstance(identity,dict) or not ORG.fullmatch(identity.get('org_id') or ''):
        return []
    urls=[('site:.gov "orgId='+identity['org_id']+'"')]
    portal=identity.get('portal_url_key')
    base=identity.get('portal_base_url')
    if base=='maps.arcgis.com' and isinstance(portal,str) and PORTAL.fullmatch(portal):
        urls.append('site:.gov "'+portal.lower()+'.maps.arcgis.com"')
    item=identity.get('original_service_item_id')
    if isinstance(item,str) and ITEM_ID.fullmatch(item):
        urls.append('site:.gov "'+item.lower()+'"')
    return urls[:3]

def web_results(query,provider,search=search_provider):
    """Bounded public search hints; original .gov page is always re-fetched."""
    if provider=='bing-rss':
        endpoint='https://www.bing.com/search?format=rss&q='+quote(query)
    elif provider=='ddg-html':
        endpoint='https://html.duckduckgo.com/html/?q='+quote(query)
    else:
        raise ValueError('Unapproved public search engine')
    received,found=search((provider,endpoint))
    if received!=provider or not isinstance(found,list):
        raise ValueError('Public search results unavailable or untrusted')
    return found[:MAX_RESULTS_PER_SEARCH]

def bing_rss(query,search=search_provider):
    return web_results(query,'bing-rss',search)

def gov_pages(queries,search=search_provider):
    """Only exact original .gov HTTPS results, not search-engine snippets."""
    result=[]
    for query in queries:
        before=len(result)
        # A missing Bing index page is a discovery gap, not proof no agency
        # has disclosed it. Query public DuckDuckGo HTML as bounded fallback.
        for provider in ('bing-rss','ddg-html'):
            if provider=='ddg-html' and len(result)>before:
                break
            try:
                found=web_results(query,provider,search)
            except Exception:
                continue
            for raw in found:
                if not isinstance(raw,str):
                    continue
                try:
                    if urlsplit(raw).fragment:
                        continue
                    url=normalize_url(raw)
                    if (not url or not is_gov(url) or
                        urlsplit(url).query or len(url)>1200):
                        continue
                    if url not in result:
                        result.append(url)
                    if len(result)>=MAX_GOV_FETCHES_PER_RUN:
                        return result
                except ValueError:
                    continue
    return result

def evaluate_page(original,identity,page,document):
    """Government article with exact Esri portal link is a *lead*, not trust."""
    org_link=linked_government_org(document,page,identity)
    item_link=linked_original_esri_service_item(document,page,identity)
    if not org_link and not item_link:
        return 'no_exact_government_to_publisher_link'
    content=' '.join(document.text)[:500000]
    mechanism='org' if org_link else 'feature_service_item'
    # Even if a government website links an exact ArcGIS item, agency
    # endorsement and operational Flock equipment remain separate questions.
    if FLOCK.search(content) and GOV_CAMERA.search(content):
        return 'agency_page_links_exact_esri_'+mechanism+'_and_mentions_flock'
    return 'agency_page_links_exact_esri_'+mechanism+'_only_no_flock_evidence'

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
            try:
                exact_item=inspect_original_service_item(url,identity.get('owner'))
            except Exception:
                exact_item=None
            if exact_item:
                identity={**identity,'original_service_item_id':exact_item}
                queries=queries_for_identity(identity)
                results['exact_esri_service_item_identified']+=1
            pages=gov_pages(queries,search)
            results['government_search_results']+=len(pages)
            for page in pages:
                if page not in seen_pages and len(seen_pages)>=MAX_GOV_FETCHES_PER_RUN:
                    results['bounded_search_page_budget_reached']+=1
                    break
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
