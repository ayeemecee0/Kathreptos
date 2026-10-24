"""Discover municipality-published links to Flock camera GIS layers.

Only original government pages already associated with *verified* Flock agenda
mentions or verified official GIS sources are entry points. An ordinary
legislative mention does not prove deployment. Candidate GIS links are PRIVATE,
never authority promotions or public camera coordinates.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
from collections import Counter

from auto_verify_flock_agenda import api_request
from government_domain_registry import (
    load_approved_domains, official_url, public_dns, valid_https_url,
)

MAX_PAGES=60
MAX_BYTES=600_000
MAX_HREFS=350
FLOCK=re.compile(r'\bflock\s+safety\b|\bflock\s+cameras?\b|\bflock\b.{0,40}\b(?:alpr|license[ -]plate)\b',re.I)
GIS_LINK=re.compile(r'/(?:FeatureServer|MapServer)/\d+/?$',re.I)
GIS_SERVICE_ROOT=re.compile(r'/(?:FeatureServer|MapServer)/?$',re.I)
LINK_LABEL=re.compile(r'\b(flock|alpr|cameras?|gis|map|location)\b',re.I)
WORTH_FOLLOWING=re.compile(r'\b(flock|alpr|camera|mapping)\b',re.I)
CAMERAS=re.compile(r'\b(camera|license plate|alpr|lpr)\b',re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Untrusted external page redirected')


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors=[]
        self.text=[]
        self.prose_text=[]  # Original page prose excluding hyperlink labels
        self.href=None
        self.anchor_content=[]
        self.hidden=0
    def handle_starttag(self,tag,attrs):
        props=dict(attrs)
        if tag in ('script','style','noscript'):
            self.hidden+=1
        if tag=='a' and self.href is None:
            self.href=props.get('href')
            self.anchor_content=[]
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            if len(self.anchors)<MAX_HREFS:
                self.anchors.append((self.href,' '.join(self.anchor_content).strip()))
            self.href=None
            self.anchor_content=[]
        if tag in ('script','style','noscript') and self.hidden:
            self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:
            self.text.append(data)
            if self.href is None:
                self.prose_text.append(data)
            else:
                self.anchor_content.append(data)


def normalized_url(url):
    p=valid_https_url(url)
    if not p or p.fragment or len(url)>1500:
        return None
    if p.port not in (None,443) or p.username or p.password:
        return None
    return urllib.parse.urlunsplit(('https',p.hostname,p.path or '/',p.query,''))


def approved_page(url,approved,authoritative_pages):
    normalized=normalized_url(url)
    if not normalized or normalized not in authoritative_pages:
        return False
    # Original authority is the exact database-verified page, not a search hit.
    return bool(official_url(normalized,approved) or
                normalized in authoritative_pages['trusted_gis'])


def get_seed_pages(approved):
    verified=api_request(
      'trusted_flock_gis_sources?select=government_evidence_url,jurisdiction_label,'
      'source_status&source_status=eq.verified&limit=100')
    agendas=api_request(
      'verified_flock_agenda_mentions?select=government_evidence_url,jurisdiction_label,'
      'matter_title,status&status=eq.verified&limit=150')
    if not isinstance(verified,list) or not isinstance(agendas,list) or len(verified)>=100 or len(agendas)>=150:
        raise ValueError('Verified original government disclosure seed registry unavailable or truncated')
    roots={}
    trusted=set()
    for item in verified:
        url=normalized_url(item.get('government_evidence_url') or '')
        if url:
            roots[url]=item['jurisdiction_label']
            trusted.add(url)
    for item in agendas:
        if not FLOCK.search(str(item.get('matter_title') or '')):
            continue
        url=normalized_url(item.get('government_evidence_url') or '')
        if url and official_url(url,approved):
            roots.setdefault(url,item['jurisdiction_label'])
    # Government pages must be reached by exact seed, not arbitrary offsite pages.
    return list(sorted(roots.items()))[:MAX_PAGES],trusted


def fetch_government_page(url):
    p=valid_https_url(url)
    if (not p or p.fragment or not public_dns(p.hostname) or p.port not in (None,443)
        or len(url)>1500):
        raise ValueError('Government page host is not a safe HTTPS public destination')
    opener=urllib.request.build_opener(NoRedirect)
    request=urllib.request.Request(url,headers={
        'User-Agent':'Katoptron/1.0 civic transparency research',
        'Accept':'text/html'
    })
    with opener.open(request,timeout=15) as response:
        if response.geturl()!=url:
            raise ValueError('Government page was redirected')
        if not response.headers.get('Content-Type','').lower().startswith('text/html'):
            raise ValueError('Government disclosure is not HTML')
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES or not data:
        raise ValueError('Original government disclosure missing or oversized')
    parsed=Anchors()
    parsed.feed(data.decode('utf8','replace'))
    return parsed,hashlib.sha256(data).hexdigest()


def original_disclosure_text(document):
    """Use original body prose, not potentially untrusted linked map titles."""
    return ' '.join(getattr(document,'prose_text',[]))[:MAX_BYTES]


def original_camera_disclosure(document):
    prose=original_disclosure_text(document)
    return bool(FLOCK.search(prose) and CAMERAS.search(prose))


def gis_candidate_links(document,page,scope,method,jurisdiction,sha):
    if not original_camera_disclosure(document):
        return []
    found=[]
    for raw,label in document.anchors:
        absolute=urllib.parse.urljoin(page,raw or '')
        url=normalized_url(absolute)
        if not url or not GIS_LINK.search(urllib.parse.urlsplit(url).path):
            continue
        if not LINK_LABEL.search(label+' '+urllib.parse.urlsplit(url).path):
            continue
        p=urllib.parse.urlsplit(url)
        found.append({
            'disclosure_url':page,
            'gis_layer_url':url.rstrip('/'),
            'jurisdiction_label':jurisdiction,
            'discovery_method':method,
            'link_label':(' '.join(label.split()) or 'Flock GIS camera layer')[:220],
            'government_page_sha256':sha,
            'source_host_scope':scope,
            'layer_host':p.hostname,
        })
    return found


def same_site_page_links(document,page,host):
    selected=[]
    for raw,label in document.anchors:
        if not WORTH_FOLLOWING.search(label):
            continue
        target=normalized_url(urllib.parse.urljoin(page,raw or ''))
        if target and urllib.parse.urlsplit(target).hostname==host and target!=page and target not in selected:
            selected.append(target)
        if len(selected)>=3:
            break
    return selected


def stage(rows):
    for row in rows:
        result=api_request(
            'government_gis_disclosure_leads?on_conflict=disclosure_url,gis_layer_url',
            method='POST',payload=[row],
            prefer='resolution=ignore-duplicates,return=minimal')
        if result is not None:
            raise ValueError('Unexpected private government GIS link insertion receipt')


def same_original_gov_apex(page,layer):
    """Exact .gov-to-.gov GIS trust boundary, without importing verifier IO."""
    p=urllib.parse.urlsplit(page)
    l=urllib.parse.urlsplit(layer)
    if (p.scheme!='https' or l.scheme!='https' or
        p.username or p.password or l.username or l.password or
        p.port is not None or l.port is not None or
        l.query or l.fragment or not p.hostname or not l.hostname or
        not (GIS_LINK.search(l.path) or GIS_SERVICE_ROOT.search(l.path))):
        return False
    first=p.hostname.lower().split('.')
    second=l.hostname.lower().split('.')
    return (len(first)>=3 and len(second)>=3 and
            first[-1]==second[-1]=='gov' and first[-2:]==second[-2:])


def directly_linked_original_gov_service_roots(document,page):
    """Queue bounded original .gov ArcGIS service roots for later exact-layer proof.

    A service root is only a private lead; the separate verifier requires a
    unique Flock point layer and live original-page revalidation.
    """
    if not original_camera_disclosure(document):
        return []
    found=[]
    for raw,label in document.anchors:
        if not isinstance(raw,str) or len(raw)>1500:
            continue
        link=normalized_url(urllib.parse.urljoin(page,raw))
        if not link:
            continue
        path=urllib.parse.urlsplit(link).path
        if (not GIS_SERVICE_ROOT.search(path) or
            not LINK_LABEL.search((label or '')+' '+path) or
            not same_original_gov_apex(page,link)):
            continue
        link=link.rstrip('/')
        if link not in found:
            found.append(link)
        if len(found)>=25:
            break
    return found


def stage_same_gov_flock_page(item):
    """Queue only original evidence, preserving the existing restricted RPC.

    This intentionally avoids importing the national search worker (and its
    optional feedparser dependency) into a single-purpose GIS workflow.
    """
    lookup='government_gis_search_queue?'+urllib.parse.urlencode({
        'select':'page_sha256,gis_links',
        'page_url':'eq.'+item['page_url'],'limit':'2'})
    rows=api_request(lookup)
    if not isinstance(rows,list) or len(rows)>1:
        raise ValueError('Original government GIS queue ambiguous')
    if rows:
        previous=rows[0].get('page_sha256')
        if not isinstance(previous,str) or not re.fullmatch('[a-f0-9]{64}',previous):
            raise ValueError('Original government GIS page digest invalid')
        receipt=api_request('rpc/refresh_original_government_gis_search_lead',
          method='POST',payload={
              'p_page_url':item['page_url'],
              'p_expected_previous_sha':previous,
              'p_current_page_sha':item['page_sha256'],
              'p_gis_links':item['gis_links']})
        if receipt is not True:
            raise ValueError('Original government GIS refresh refused')
    else:
        receipt=api_request('government_gis_search_queue?on_conflict=page_url',
            method='POST',payload=[item],
            prefer='resolution=ignore-duplicates,return=minimal')
        if receipt is not None:
            raise ValueError('Unexpected original government GIS queue receipt')


def scan(dry_run=False):
    approved=load_approved_domains()
    seeds,trusted=get_seed_pages(approved)
    counters=Counter()
    links={}
    # Connect the government-link lead ledger to the already restricted .gov
    # registration queue. No source trust or camera location is granted here.
    queue_pages={}
    for page,jurisdiction in seeds:
        try:
            p=urllib.parse.urlsplit(page)
            # A reviewed government GIS source page may be a custom domain.
            if page not in trusted and not official_url(page,approved):
                continue
            document,sha=fetch_government_page(page)
            pages=[(document,sha,page,'government_page_direct_anchor_v1')]
            if original_camera_disclosure(document):
                for sub in same_site_page_links(document,page,p.hostname):
                    try:
                        doc,checksum=fetch_government_page(sub)
                        pages.append((doc,checksum,sub,'government_page_same_host_depth1_v1'))
                    except Exception:
                        counters['subpages_held']+=1
            for doc,checksum,url,method in pages:
                items=gis_candidate_links(doc,url,p.hostname,method,jurisdiction,checksum)
                for item in items:
                    links[(item['disclosure_url'],item['gis_layer_url'])]=item
                # Only a freshly fetched .gov page's EXACT same-apex .gov
                # links may enter the existing nationwide GIS queue. A
                # custom-domain or external Esri layer remains a private
                # investigation lead, never an automatic government root.
                if (urllib.parse.urlsplit(url).hostname.endswith('.gov')
                    and original_camera_disclosure(doc)):
                    layers={row['gis_layer_url'] for row in items
                            if same_original_gov_apex(url,row['gis_layer_url'])}
                    services=set(directly_linked_original_gov_service_roots(doc,url))
                    counters['private_original_service_roots_found']+=len(services)
                    direct=sorted(layers|services)[:25]
                    if direct:
                        excerpt=' '.join(' '.join(doc.text).split())[:580]
                        queue_pages[url]={
                            'page_url':url,'state_search_hint':'Original government GIS disclosure',
                            'discovery_query':'Original government Flock camera point GIS link',
                            'page_sha256':checksum,'gis_links':direct[:25],
                            'evidence_excerpt':excerpt if len(excerpt)>=12 else
                                'Original government webpage discloses Flock Safety camera map.'
                        }
            counters['pages_checked']+=1
        except Exception as exc:
            counters['pages_held']+=1
            print('Government source unavailable:',urllib.parse.urlsplit(page).hostname,
                  type(exc).__name__,str(exc)[:90])
    candidates=list(links.values())
    if not dry_run and candidates:
        stage(candidates)
    if not dry_run and queue_pages:
        # Use nationwide queue's existing owner-restricted insert/refresh RPC;
        # the verifier still re-fetches the source and checks all camera IDs.
        for item in queue_pages.values():
            stage_same_gov_flock_page(item)
    counters['original_gov_pages_queued']=len(queue_pages)
    counters['gis_links_found']=len(candidates)
    counters['submitted']=0 if dry_run else len(candidates)
    for key in ('pages_checked','pages_held','subpages_held','gis_links_found','private_original_service_roots_found','original_gov_pages_queued','submitted'):
        print('Government GIS link discovery',key+':',counters[key])
    print('Newly authorized sources from unreviewed government links: 0')
    print('Camera coordinates auto-published by this crawler: 0')
    return counters


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--dry-run',action='store_true')
    import sys
    result=scan(dry_run=args.parse_args().dry_run)
    if result["pages_checked"]==0: sys.exit("No government source pages could be examined; do not report success")
,re.I)
GIS_SERVICE_ROOT=re.compile(r'/(?:FeatureServer|MapServer)/?
LINK_LABEL=re.compile(r'\b(flock|alpr|cameras?|gis|map|location)\b',re.I)
WORTH_FOLLOWING=re.compile(r'\b(flock|alpr|camera|mapping)\b',re.I)
CAMERAS=re.compile(r'\b(camera|license plate|alpr|lpr)\b',re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Untrusted external page redirected')


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors=[]
        self.text=[]
        self.prose_text=[]  # Original page prose excluding hyperlink labels
        self.href=None
        self.anchor_content=[]
        self.hidden=0
    def handle_starttag(self,tag,attrs):
        props=dict(attrs)
        if tag in ('script','style','noscript'):
            self.hidden+=1
        if tag=='a' and self.href is None:
            self.href=props.get('href')
            self.anchor_content=[]
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            if len(self.anchors)<MAX_HREFS:
                self.anchors.append((self.href,' '.join(self.anchor_content).strip()))
            self.href=None
            self.anchor_content=[]
        if tag in ('script','style','noscript') and self.hidden:
            self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:
            self.text.append(data)
            if self.href is None:
                self.prose_text.append(data)
            else:
                self.anchor_content.append(data)


def normalized_url(url):
    p=valid_https_url(url)
    if not p or p.fragment or len(url)>1500:
        return None
    if p.port not in (None,443) or p.username or p.password:
        return None
    return urllib.parse.urlunsplit(('https',p.hostname,p.path or '/',p.query,''))


def approved_page(url,approved,authoritative_pages):
    normalized=normalized_url(url)
    if not normalized or normalized not in authoritative_pages:
        return False
    # Original authority is the exact database-verified page, not a search hit.
    return bool(official_url(normalized,approved) or
                normalized in authoritative_pages['trusted_gis'])


def get_seed_pages(approved):
    verified=api_request(
      'trusted_flock_gis_sources?select=government_evidence_url,jurisdiction_label,'
      'source_status&source_status=eq.verified&limit=100')
    agendas=api_request(
      'verified_flock_agenda_mentions?select=government_evidence_url,jurisdiction_label,'
      'matter_title,status&status=eq.verified&limit=150')
    if not isinstance(verified,list) or not isinstance(agendas,list) or len(verified)>=100 or len(agendas)>=150:
        raise ValueError('Verified original government disclosure seed registry unavailable or truncated')
    roots={}
    trusted=set()
    for item in verified:
        url=normalized_url(item.get('government_evidence_url') or '')
        if url:
            roots[url]=item['jurisdiction_label']
            trusted.add(url)
    for item in agendas:
        if not FLOCK.search(str(item.get('matter_title') or '')):
            continue
        url=normalized_url(item.get('government_evidence_url') or '')
        if url and official_url(url,approved):
            roots.setdefault(url,item['jurisdiction_label'])
    # Government pages must be reached by exact seed, not arbitrary offsite pages.
    return list(sorted(roots.items()))[:MAX_PAGES],trusted


def fetch_government_page(url):
    p=valid_https_url(url)
    if (not p or p.fragment or not public_dns(p.hostname) or p.port not in (None,443)
        or len(url)>1500):
        raise ValueError('Government page host is not a safe HTTPS public destination')
    opener=urllib.request.build_opener(NoRedirect)
    request=urllib.request.Request(url,headers={
        'User-Agent':'Katoptron/1.0 civic transparency research',
        'Accept':'text/html'
    })
    with opener.open(request,timeout=15) as response:
        if response.geturl()!=url:
            raise ValueError('Government page was redirected')
        if not response.headers.get('Content-Type','').lower().startswith('text/html'):
            raise ValueError('Government disclosure is not HTML')
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES or not data:
        raise ValueError('Original government disclosure missing or oversized')
    parsed=Anchors()
    parsed.feed(data.decode('utf8','replace'))
    return parsed,hashlib.sha256(data).hexdigest()


def original_disclosure_text(document):
    """Use original body prose, not potentially untrusted linked map titles."""
    return ' '.join(getattr(document,'prose_text',[]))[:MAX_BYTES]


def original_camera_disclosure(document):
    prose=original_disclosure_text(document)
    return bool(FLOCK.search(prose) and CAMERAS.search(prose))


def gis_candidate_links(document,page,scope,method,jurisdiction,sha):
    if not original_camera_disclosure(document):
        return []
    found=[]
    for raw,label in document.anchors:
        absolute=urllib.parse.urljoin(page,raw or '')
        url=normalized_url(absolute)
        if not url or not GIS_LINK.search(urllib.parse.urlsplit(url).path):
            continue
        if not LINK_LABEL.search(label+' '+urllib.parse.urlsplit(url).path):
            continue
        p=urllib.parse.urlsplit(url)
        found.append({
            'disclosure_url':page,
            'gis_layer_url':url.rstrip('/'),
            'jurisdiction_label':jurisdiction,
            'discovery_method':method,
            'link_label':(' '.join(label.split()) or 'Flock GIS camera layer')[:220],
            'government_page_sha256':sha,
            'source_host_scope':scope,
            'layer_host':p.hostname,
        })
    return found


def same_site_page_links(document,page,host):
    selected=[]
    for raw,label in document.anchors:
        if not WORTH_FOLLOWING.search(label):
            continue
        target=normalized_url(urllib.parse.urljoin(page,raw or ''))
        if target and urllib.parse.urlsplit(target).hostname==host and target!=page and target not in selected:
            selected.append(target)
        if len(selected)>=3:
            break
    return selected


def stage(rows):
    for row in rows:
        result=api_request(
            'government_gis_disclosure_leads?on_conflict=disclosure_url,gis_layer_url',
            method='POST',payload=[row],
            prefer='resolution=ignore-duplicates,return=minimal')
        if result is not None:
            raise ValueError('Unexpected private government GIS link insertion receipt')


def same_original_gov_apex(page,layer):
    """Exact .gov-to-.gov GIS trust boundary, without importing verifier IO."""
    p=urllib.parse.urlsplit(page)
    l=urllib.parse.urlsplit(layer)
    if (p.scheme!='https' or l.scheme!='https' or
        p.username or p.password or l.username or l.password or
        p.port is not None or l.port is not None or
        l.query or l.fragment or not p.hostname or not l.hostname or
        not GIS_LINK.search(l.path)):
        return False
    first=p.hostname.lower().split('.')
    second=l.hostname.lower().split('.')
    return (len(first)>=3 and len(second)>=3 and
            first[-1]==second[-1]=='gov' and first[-2:]==second[-2:])


def stage_same_gov_flock_page(item):
    """Queue only original evidence, preserving the existing restricted RPC.

    This intentionally avoids importing the national search worker (and its
    optional feedparser dependency) into a single-purpose GIS workflow.
    """
    lookup='government_gis_search_queue?'+urllib.parse.urlencode({
        'select':'page_sha256,gis_links',
        'page_url':'eq.'+item['page_url'],'limit':'2'})
    rows=api_request(lookup)
    if not isinstance(rows,list) or len(rows)>1:
        raise ValueError('Original government GIS queue ambiguous')
    if rows:
        previous=rows[0].get('page_sha256')
        if not isinstance(previous,str) or not re.fullmatch('[a-f0-9]{64}',previous):
            raise ValueError('Original government GIS page digest invalid')
        receipt=api_request('rpc/refresh_original_government_gis_search_lead',
          method='POST',payload={
              'p_page_url':item['page_url'],
              'p_expected_previous_sha':previous,
              'p_current_page_sha':item['page_sha256'],
              'p_gis_links':item['gis_links']})
        if receipt is not True:
            raise ValueError('Original government GIS refresh refused')
    else:
        receipt=api_request('government_gis_search_queue?on_conflict=page_url',
            method='POST',payload=[item],
            prefer='resolution=ignore-duplicates,return=minimal')
        if receipt is not None:
            raise ValueError('Unexpected original government GIS queue receipt')


def scan(dry_run=False):
    approved=load_approved_domains()
    seeds,trusted=get_seed_pages(approved)
    counters=Counter()
    links={}
    # Connect the government-link lead ledger to the already restricted .gov
    # registration queue. No source trust or camera location is granted here.
    queue_pages={}
    for page,jurisdiction in seeds:
        try:
            p=urllib.parse.urlsplit(page)
            # A reviewed government GIS source page may be a custom domain.
            if page not in trusted and not official_url(page,approved):
                continue
            document,sha=fetch_government_page(page)
            pages=[(document,sha,page,'government_page_direct_anchor_v1')]
            if original_camera_disclosure(document):
                for sub in same_site_page_links(document,page,p.hostname):
                    try:
                        doc,checksum=fetch_government_page(sub)
                        pages.append((doc,checksum,sub,'government_page_same_host_depth1_v1'))
                    except Exception:
                        counters['subpages_held']+=1
            for doc,checksum,url,method in pages:
                items=gis_candidate_links(doc,url,p.hostname,method,jurisdiction,checksum)
                for item in items:
                    links[(item['disclosure_url'],item['gis_layer_url'])]=item
                # Only a freshly fetched .gov page's EXACT same-apex .gov
                # links may enter the existing nationwide GIS queue. A
                # custom-domain or external Esri layer remains a private
                # investigation lead, never an automatic government root.
                if (items and urllib.parse.urlsplit(url).hostname.endswith('.gov')
                    and original_camera_disclosure(doc)):
                    direct=sorted({row['gis_layer_url'] for row in items
                                   if same_original_gov_apex(url,row['gis_layer_url'])})
                    if direct:
                        excerpt=' '.join(' '.join(doc.text).split())[:580]
                        queue_pages[url]={
                            'page_url':url,'state_search_hint':'Original government GIS disclosure',
                            'discovery_query':'Original government Flock camera point GIS link',
                            'page_sha256':checksum,'gis_links':direct[:25],
                            'evidence_excerpt':excerpt if len(excerpt)>=12 else
                                'Original government webpage discloses Flock Safety camera map.'
                        }
            counters['pages_checked']+=1
        except Exception as exc:
            counters['pages_held']+=1
            print('Government source unavailable:',urllib.parse.urlsplit(page).hostname,
                  type(exc).__name__,str(exc)[:90])
    candidates=list(links.values())
    if not dry_run and candidates:
        stage(candidates)
    if not dry_run and queue_pages:
        # Use nationwide queue's existing owner-restricted insert/refresh RPC;
        # the verifier still re-fetches the source and checks all camera IDs.
        for item in queue_pages.values():
            stage_same_gov_flock_page(item)
    counters['original_gov_pages_queued']=len(queue_pages)
    counters['gis_links_found']=len(candidates)
    counters['submitted']=0 if dry_run else len(candidates)
    for key in ('pages_checked','pages_held','subpages_held','gis_links_found','original_gov_pages_queued','submitted'):
        print('Government GIS link discovery',key+':',counters[key])
    print('Newly authorized sources from unreviewed government links: 0')
    print('Camera coordinates auto-published by this crawler: 0')
    return counters


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--dry-run',action='store_true')
    import sys
    result=scan(dry_run=args.parse_args().dry_run)
    if result["pages_checked"]==0: sys.exit("No government source pages could be examined; do not report success")
,re.I)
LINK_LABEL=re.compile(r'\b(flock|alpr|cameras?|gis|map|location)\b',re.I)
WORTH_FOLLOWING=re.compile(r'\b(flock|alpr|camera|mapping)\b',re.I)
CAMERAS=re.compile(r'\b(camera|license plate|alpr|lpr)\b',re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Untrusted external page redirected')


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors=[]
        self.text=[]
        self.prose_text=[]  # Original page prose excluding hyperlink labels
        self.href=None
        self.anchor_content=[]
        self.hidden=0
    def handle_starttag(self,tag,attrs):
        props=dict(attrs)
        if tag in ('script','style','noscript'):
            self.hidden+=1
        if tag=='a' and self.href is None:
            self.href=props.get('href')
            self.anchor_content=[]
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            if len(self.anchors)<MAX_HREFS:
                self.anchors.append((self.href,' '.join(self.anchor_content).strip()))
            self.href=None
            self.anchor_content=[]
        if tag in ('script','style','noscript') and self.hidden:
            self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:
            self.text.append(data)
            if self.href is None:
                self.prose_text.append(data)
            else:
                self.anchor_content.append(data)


def normalized_url(url):
    p=valid_https_url(url)
    if not p or p.fragment or len(url)>1500:
        return None
    if p.port not in (None,443) or p.username or p.password:
        return None
    return urllib.parse.urlunsplit(('https',p.hostname,p.path or '/',p.query,''))


def approved_page(url,approved,authoritative_pages):
    normalized=normalized_url(url)
    if not normalized or normalized not in authoritative_pages:
        return False
    # Original authority is the exact database-verified page, not a search hit.
    return bool(official_url(normalized,approved) or
                normalized in authoritative_pages['trusted_gis'])


def get_seed_pages(approved):
    verified=api_request(
      'trusted_flock_gis_sources?select=government_evidence_url,jurisdiction_label,'
      'source_status&source_status=eq.verified&limit=100')
    agendas=api_request(
      'verified_flock_agenda_mentions?select=government_evidence_url,jurisdiction_label,'
      'matter_title,status&status=eq.verified&limit=150')
    if not isinstance(verified,list) or not isinstance(agendas,list) or len(verified)>=100 or len(agendas)>=150:
        raise ValueError('Verified original government disclosure seed registry unavailable or truncated')
    roots={}
    trusted=set()
    for item in verified:
        url=normalized_url(item.get('government_evidence_url') or '')
        if url:
            roots[url]=item['jurisdiction_label']
            trusted.add(url)
    for item in agendas:
        if not FLOCK.search(str(item.get('matter_title') or '')):
            continue
        url=normalized_url(item.get('government_evidence_url') or '')
        if url and official_url(url,approved):
            roots.setdefault(url,item['jurisdiction_label'])
    # Government pages must be reached by exact seed, not arbitrary offsite pages.
    return list(sorted(roots.items()))[:MAX_PAGES],trusted


def fetch_government_page(url):
    p=valid_https_url(url)
    if (not p or p.fragment or not public_dns(p.hostname) or p.port not in (None,443)
        or len(url)>1500):
        raise ValueError('Government page host is not a safe HTTPS public destination')
    opener=urllib.request.build_opener(NoRedirect)
    request=urllib.request.Request(url,headers={
        'User-Agent':'Katoptron/1.0 civic transparency research',
        'Accept':'text/html'
    })
    with opener.open(request,timeout=15) as response:
        if response.geturl()!=url:
            raise ValueError('Government page was redirected')
        if not response.headers.get('Content-Type','').lower().startswith('text/html'):
            raise ValueError('Government disclosure is not HTML')
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES or not data:
        raise ValueError('Original government disclosure missing or oversized')
    parsed=Anchors()
    parsed.feed(data.decode('utf8','replace'))
    return parsed,hashlib.sha256(data).hexdigest()


def original_disclosure_text(document):
    """Use original body prose, not potentially untrusted linked map titles."""
    return ' '.join(getattr(document,'prose_text',[]))[:MAX_BYTES]


def original_camera_disclosure(document):
    prose=original_disclosure_text(document)
    return bool(FLOCK.search(prose) and CAMERAS.search(prose))


def gis_candidate_links(document,page,scope,method,jurisdiction,sha):
    if not original_camera_disclosure(document):
        return []
    found=[]
    for raw,label in document.anchors:
        absolute=urllib.parse.urljoin(page,raw or '')
        url=normalized_url(absolute)
        if not url or not GIS_LINK.search(urllib.parse.urlsplit(url).path):
            continue
        if not LINK_LABEL.search(label+' '+urllib.parse.urlsplit(url).path):
            continue
        p=urllib.parse.urlsplit(url)
        found.append({
            'disclosure_url':page,
            'gis_layer_url':url.rstrip('/'),
            'jurisdiction_label':jurisdiction,
            'discovery_method':method,
            'link_label':(' '.join(label.split()) or 'Flock GIS camera layer')[:220],
            'government_page_sha256':sha,
            'source_host_scope':scope,
            'layer_host':p.hostname,
        })
    return found


def same_site_page_links(document,page,host):
    selected=[]
    for raw,label in document.anchors:
        if not WORTH_FOLLOWING.search(label):
            continue
        target=normalized_url(urllib.parse.urljoin(page,raw or ''))
        if target and urllib.parse.urlsplit(target).hostname==host and target!=page and target not in selected:
            selected.append(target)
        if len(selected)>=3:
            break
    return selected


def stage(rows):
    for row in rows:
        result=api_request(
            'government_gis_disclosure_leads?on_conflict=disclosure_url,gis_layer_url',
            method='POST',payload=[row],
            prefer='resolution=ignore-duplicates,return=minimal')
        if result is not None:
            raise ValueError('Unexpected private government GIS link insertion receipt')


def same_original_gov_apex(page,layer):
    """Exact .gov-to-.gov GIS trust boundary, without importing verifier IO."""
    p=urllib.parse.urlsplit(page)
    l=urllib.parse.urlsplit(layer)
    if (p.scheme!='https' or l.scheme!='https' or
        p.username or p.password or l.username or l.password or
        p.port is not None or l.port is not None or
        l.query or l.fragment or not p.hostname or not l.hostname or
        not GIS_LINK.search(l.path)):
        return False
    first=p.hostname.lower().split('.')
    second=l.hostname.lower().split('.')
    return (len(first)>=3 and len(second)>=3 and
            first[-1]==second[-1]=='gov' and first[-2:]==second[-2:])


def stage_same_gov_flock_page(item):
    """Queue only original evidence, preserving the existing restricted RPC.

    This intentionally avoids importing the national search worker (and its
    optional feedparser dependency) into a single-purpose GIS workflow.
    """
    lookup='government_gis_search_queue?'+urllib.parse.urlencode({
        'select':'page_sha256,gis_links',
        'page_url':'eq.'+item['page_url'],'limit':'2'})
    rows=api_request(lookup)
    if not isinstance(rows,list) or len(rows)>1:
        raise ValueError('Original government GIS queue ambiguous')
    if rows:
        previous=rows[0].get('page_sha256')
        if not isinstance(previous,str) or not re.fullmatch('[a-f0-9]{64}',previous):
            raise ValueError('Original government GIS page digest invalid')
        receipt=api_request('rpc/refresh_original_government_gis_search_lead',
          method='POST',payload={
              'p_page_url':item['page_url'],
              'p_expected_previous_sha':previous,
              'p_current_page_sha':item['page_sha256'],
              'p_gis_links':item['gis_links']})
        if receipt is not True:
            raise ValueError('Original government GIS refresh refused')
    else:
        receipt=api_request('government_gis_search_queue?on_conflict=page_url',
            method='POST',payload=[item],
            prefer='resolution=ignore-duplicates,return=minimal')
        if receipt is not None:
            raise ValueError('Unexpected original government GIS queue receipt')


def scan(dry_run=False):
    approved=load_approved_domains()
    seeds,trusted=get_seed_pages(approved)
    counters=Counter()
    links={}
    # Connect the government-link lead ledger to the already restricted .gov
    # registration queue. No source trust or camera location is granted here.
    queue_pages={}
    for page,jurisdiction in seeds:
        try:
            p=urllib.parse.urlsplit(page)
            # A reviewed government GIS source page may be a custom domain.
            if page not in trusted and not official_url(page,approved):
                continue
            document,sha=fetch_government_page(page)
            pages=[(document,sha,page,'government_page_direct_anchor_v1')]
            if original_camera_disclosure(document):
                for sub in same_site_page_links(document,page,p.hostname):
                    try:
                        doc,checksum=fetch_government_page(sub)
                        pages.append((doc,checksum,sub,'government_page_same_host_depth1_v1'))
                    except Exception:
                        counters['subpages_held']+=1
            for doc,checksum,url,method in pages:
                items=gis_candidate_links(doc,url,p.hostname,method,jurisdiction,checksum)
                for item in items:
                    links[(item['disclosure_url'],item['gis_layer_url'])]=item
                # Only a freshly fetched .gov page's EXACT same-apex .gov
                # links may enter the existing nationwide GIS queue. A
                # custom-domain or external Esri layer remains a private
                # investigation lead, never an automatic government root.
                if (items and urllib.parse.urlsplit(url).hostname.endswith('.gov')
                    and original_camera_disclosure(doc)):
                    direct=sorted({row['gis_layer_url'] for row in items
                                   if same_original_gov_apex(url,row['gis_layer_url'])})
                    if direct:
                        excerpt=' '.join(' '.join(doc.text).split())[:580]
                        queue_pages[url]={
                            'page_url':url,'state_search_hint':'Original government GIS disclosure',
                            'discovery_query':'Original government Flock camera point GIS link',
                            'page_sha256':checksum,'gis_links':direct[:25],
                            'evidence_excerpt':excerpt if len(excerpt)>=12 else
                                'Original government webpage discloses Flock Safety camera map.'
                        }
            counters['pages_checked']+=1
        except Exception as exc:
            counters['pages_held']+=1
            print('Government source unavailable:',urllib.parse.urlsplit(page).hostname,
                  type(exc).__name__,str(exc)[:90])
    candidates=list(links.values())
    if not dry_run and candidates:
        stage(candidates)
    if not dry_run and queue_pages:
        # Use nationwide queue's existing owner-restricted insert/refresh RPC;
        # the verifier still re-fetches the source and checks all camera IDs.
        for item in queue_pages.values():
            stage_same_gov_flock_page(item)
    counters['original_gov_pages_queued']=len(queue_pages)
    counters['gis_links_found']=len(candidates)
    counters['submitted']=0 if dry_run else len(candidates)
    for key in ('pages_checked','pages_held','subpages_held','gis_links_found','original_gov_pages_queued','submitted'):
        print('Government GIS link discovery',key+':',counters[key])
    print('Newly authorized sources from unreviewed government links: 0')
    print('Camera coordinates auto-published by this crawler: 0')
    return counters


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--dry-run',action='store_true')
    import sys
    result=scan(dry_run=args.parse_args().dry_run)
    if result["pages_checked"]==0: sys.exit("No government source pages could be examined; do not report success")
