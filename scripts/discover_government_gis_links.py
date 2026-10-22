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
FLOCK=re.compile(r'\bflock\s+safety\b|\bflock\b.{0,40}\balpr\b',re.I)
GIS_LINK=re.compile(r'/(?:FeatureServer|MapServer)/\d+/?$',re.I)
LINK_LABEL=re.compile(r'\b(flock|alpr|cameras?|gis|map|location)\b',re.I)
WORTH_FOLLOWING=re.compile(r'\b(flock|alpr|camera|mapping)\b',re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Untrusted external page redirected')


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors=[]
        self.text=[]
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
            if self.href is not None:
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


def gis_candidate_links(document,page,scope,method,jurisdiction,sha):
    if not FLOCK.search(' '.join(document.text)[:MAX_BYTES]):
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


def scan(dry_run=False):
    approved=load_approved_domains()
    seeds,trusted=get_seed_pages(approved)
    counters=Counter()
    links={}
    for page,jurisdiction in seeds:
        try:
            p=urllib.parse.urlsplit(page)
            # A reviewed government GIS source page may be a custom domain.
            if page not in trusted and not official_url(page,approved):
                continue
            document,sha=fetch_government_page(page)
            pages=[(document,sha,page,'government_page_direct_anchor_v1')]
            if FLOCK.search(' '.join(document.text)[:MAX_BYTES]):
                for sub in same_site_page_links(document,page,p.hostname):
                    try:
                        doc,checksum=fetch_government_page(sub)
                        pages.append((doc,checksum,sub,'government_page_same_host_depth1_v1'))
                    except Exception:
                        counters['subpages_held']+=1
            for doc,checksum,url,method in pages:
                for item in gis_candidate_links(doc,url,p.hostname,method,jurisdiction,checksum):
                    links[(item['disclosure_url'],item['gis_layer_url'])]=item
            counters['pages_checked']+=1
        except Exception as exc:
            counters['pages_held']+=1
            print('Government source unavailable:',urllib.parse.urlsplit(page).hostname,
                  type(exc).__name__,str(exc)[:90])
    candidates=list(links.values())
    if not dry_run and candidates:
        stage(candidates)
    counters['gis_links_found']=len(candidates)
    counters['submitted']=0 if dry_run else len(candidates)
    for key in ('pages_checked','pages_held','subpages_held','gis_links_found','submitted'):
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
