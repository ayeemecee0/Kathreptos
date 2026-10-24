"""Probe independent original-agency hyperlinks to identified Esri organizations.

An exact government-source link to an ArcGIS organization can corroborate
publisher authority even when the page does not link to the exact camera
FeatureServer. That is only a PRIVATE research lead. The individual camera
layer, ownership and exact coordinates still need source authorization.
No user locations, plate data, camera candidate URLs or credentials are logged.
"""
from collections import Counter
from urllib.parse import urlsplit, urljoin, parse_qs
import hashlib
import re

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from audit_external_arcgis_candidates import (candidate_inputs,
    inspect_arcgis_publisher,check_external,LAYER_URL)
from discover_government_gis_links import (
    fetch_government_page,get_seed_pages,normalized_url)
from government_domain_registry import load_approved_domains

MAX_PAGES=65
MAX_EXTERNAL=35
ORG_ID=re.compile(r'^[A-Za-z0-9]{8,48}$')
URL_KEY=re.compile(r'^[A-Za-z0-9-]{3,90}$')


def is_exact_esri_org_link(url,identity):
    """No generic Esri account/item name is sufficient organization evidence."""
    if not isinstance(identity,dict):
        return False
    orgid=identity.get('org_id')
    if not isinstance(orgid,str) or not ORG_ID.fullmatch(orgid):
        return False
    target=normalized_url(url)
    if not target:
        return False
    parsed=urlsplit(target)
    hostname=parsed.hostname
    if hostname in ('www.arcgis.com','arcgis.com'):
        if parsed.path.rstrip('/').lower() in ('/home/organization.html',
             '/apps/mapviewer/index.html'):
            ids=[value for k,values in parse_qs(parsed.query).items()
                 if k.lower()=='orgid' for value in values]
            return len(ids)==1 and ids[0]==orgid
        return False
    # Government pages sometimes link the agency-branded ArcGIS Online
    # homepage, not an individual Esri layer. Only the EXACT Esri-owned
    # first-party maps.arcgis.com root and matching portal key may qualify.
    key=identity.get('portal_url_key')
    base=identity.get('portal_base_url')
    if (isinstance(key,str) and URL_KEY.fullmatch(key)
        and base=='maps.arcgis.com'
        and hostname==key.lower()+'.maps.arcgis.com'
        and not parsed.query):
        return True
    return False


def linked_government_org(document,page,identity):
    found=False
    for href,label in document.anchors:
        if not isinstance(href,str) or len(href)>1500:
            continue
        url=urljoin(page,href)
        if is_exact_esri_org_link(url,identity):
            found=True
    return found


def government_pages():
    approved=load_approved_domains()
    seeded,_=get_seed_pages(approved)
    pages={url for url,label in seeded}
    gis=fetch_all(api_request,
        'government_gis_search_queue?select=page_url,candidate_status&limit=100',
        'page_url',max_records=500)
    for row in gis:
        url=row.get('page_url')
        normalized=normalized_url(url) if isinstance(url,str) else None
        parsed=urlsplit(normalized) if normalized else None
        # A bare search-page lead is only independently authoritative if it
        # is at an actual .gov hostname. Custom domains require a previously
        # owner-reviewed government source, already in the seed pages.
        if parsed and parsed.hostname and parsed.hostname.endswith('.gov'):
            pages.add(normalized)
    return sorted(pages)[:MAX_PAGES]


def run():
    candidates,receipts,verified=candidate_inputs()
    direct={x['gis_layer_url'] for x in receipts if x.get('discovery_method') in (
         'government_page_direct_anchor_v1','government_page_direct_service_v1')}
    trusted={x['gis_layer_url'] for x in verified}
    externally=[c for c in candidates
        if LAYER_URL.fullmatch(c.get('gis_layer_url') or '')]
    if len(externally)>MAX_EXTERNAL:
        raise ValueError('Too many external ArcGIS candidates for a bounded agency endorsement search')
    if not externally:
        print('ESRI GOV ORGANIZATION PROOF: no external candidates to investigate')
        return Counter()
    agency=government_pages()
    if not agency:
        raise ValueError('No independently governed original pages available')
    docs=[]
    skipped=0
    # Cache original pages once per audit, not once per each Esri candidate.
    for page in agency:
        try:
            document,digest=fetch_government_page(page)
            docs.append((page,document,digest))
        except Exception:
            skipped+=1
    if not docs:
        raise ValueError('Every original agency evidence page is unavailable')
    counts=Counter()
    counts['original_pages_checked']=len(docs)
    counts['original_pages_unavailable']=skipped
    for candidate in externally:
        url=candidate['gis_layer_url']
        marker=hashlib.sha256(url.encode()).hexdigest()[:12]
        if url in trusted:
            counts['already_verified']+=1
            continue
        # Require the actual service and per-feature point metadata to match
        # before even using an Esri organization association as a lead.
        try:
            status=check_external(candidate,direct,trusted)
            if status not in ('verified_arcgis_metadata_only_missing_original_government_link',
                              'candidate_government_link_needs_full_attestation'):
                counts['original_service_incomplete']+=1
                continue
            identity=inspect_arcgis_publisher(url,return_identity=True)
            if not isinstance(identity,dict):
                counts['arcgis_org_not_attributed']+=1
                continue
            counts['esri_org_exactly_identified']+=1
            matches=[hashlib.sha256(page.encode()).hexdigest()[:12]
                for page,document,digest in docs
                if linked_government_org(document,page,identity)]
            if matches:
                counts['gov_page_links_exact_esri_organization']+=1
                # A matched link is original-government *publisher association*
                # only, not yet an individually reviewed Flock camera location.
                print('ESRI GOV PUBLISHER MATCH',marker,'gov_page_sha',matches[0])
            else:
                counts['original_government_organization_link_missing']+=1
                print('ESRI GOV PUBLISHER HELD',marker,'no reviewed agency org hyperlink')
        except Exception as exc:
            counts['inspection_unavailable']+=1
            print('ESRI GOV PUBLISHER HELD',marker,type(exc).__name__)
    for label in sorted(counts):
        print('ESRI GOV PUBLISHER SUMMARY',label,counts[label])
    print('ESRI GOV PUBLISHER camera locations automatically verified: 0')
    print('ESRI GOV PUBLISHER source authorities automatically approved: 0')
    return counts


if __name__=='__main__':
    run()
