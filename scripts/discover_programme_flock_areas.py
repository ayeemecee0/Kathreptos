"""Verify original government Flock deployment polygons in states without pins.

A dated, already source-verified municipal Flock programme is an acceptable
independent starting point, but NOT deployment geometry. Publish an area only
when that programme's OWN fetched government HTML links an exact, same-government
GIS Flock deployment polygon. No fake city outlines, procurement-shaped
assumptions, radius buffers, traffic polygons, or camera inferences.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
import urllib.parse
import urllib.request

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from discover_government_gis_links import (
    fetch_government_page, normalized_url, NoRedirect
)
from government_domain_registry import public_dns
from discover_official_flock_areas import POLYGON

GIS=re.compile(r'^https://(?:[a-z0-9-]+\.)+gov/[A-Za-z0-9_/-]+/'
               r'(?:MapServer|FeatureServer)/[0-9]+$',re.I)
FLOCK=re.compile(r'\bflock(?:\s+safety)?\b',re.I)
CAMERAS=re.compile(r'\b(?:cameras?|alpr|license plates?)\b',re.I)
MAX_BYTES=1_500_000
MAX_LAYERS=4
MAX_POLYGONS=50


def government_programmes():
    rows=fetch_all(api_request,
        "flock_documented_programs?select=program_key,jurisdiction_label,"
        "official_evidence_url,record_status,program_status"
        "&record_status=eq.verified"
        "&program_status=eq.documented_at_source_date&limit=50",
        "program_key",max_records=200)
    return rows


def gov_apex(url):
    p=urllib.parse.urlsplit(url)
    if (p.scheme!='https' or not p.hostname or not p.hostname.endswith('.gov')
        or p.port not in (None,443) or p.username or p.password
        or p.query and len(p.query)>800):
        return None
    return '.'.join(p.hostname.lower().split('.')[-2:])


def direct_government_polygon_links(page,doc):
    if not gov_apex(page):
        return []
    text=" ".join(doc.text)
    if not FLOCK.search(text) or not CAMERAS.search(text):
        return []
    found=[]
    for raw,label in doc.anchors:
        link=normalized_url(urllib.parse.urljoin(page,raw or ''))
        if (not link or not GIS.fullmatch(link)
            or gov_apex(link)!=gov_apex(page)):
            continue
        # Link text may say "GIS map" while layer name is only available
        # in original GIS metadata; still verify metadata before acceptance.
        if not re.search(r'\b(flock|alpr|camera|gis|map|deployment|coverage)\b',
                         label or '',re.I):
            continue
        if link not in found:
            found.append(link)
        if len(found)>=MAX_LAYERS:
            break
    return found


def government_gis_json(url):
    parsed=urllib.parse.urlsplit(url)
    if (not GIS.fullmatch(url.split('?')[0]) and
        not re.fullmatch(r'^https://(?:[a-z0-9-]+\.)+gov/'
              r'[A-Za-z0-9_/-]+/(?:MapServer|FeatureServer)/[0-9]+/query$',parsed.scheme+'://'+parsed.netloc+parsed.path)):
        raise ValueError('Not an exact original government polygon metadata/query URL')
    if not public_dns(parsed.hostname):
        raise ValueError('GIS endpoint did not resolve to a public network')
    opener=urllib.request.build_opener(NoRedirect)
    request=urllib.request.Request(url,headers={
        'Accept':'application/json',
        'User-Agent':'Katoptron/1.0 original government civic records'
    })
    with opener.open(request,timeout=20) as response:
        if response.geturl()!=url:
            raise ValueError('Government GIS redirected off exact original source')
        data=response.read(MAX_BYTES+1)
    if not data or len(data)>MAX_BYTES:
        raise ValueError('Original government polygon response absent or too large')
    parsed_json=json.loads(data)
    if not isinstance(parsed_json,dict) or parsed_json.get('error'):
        raise ValueError('Original government polygon server returned an error')
    return parsed_json


def original_polygon_payloads(prog,url,page_hash):
    layer=government_gis_json(url+'?f=json')
    if (not POLYGON.fullmatch(str(layer.get('name') or ''))
        or layer.get('type')!='Feature Layer'
        or layer.get('geometryType')!='esriGeometryPolygon'):
        raise ValueError('Source GIS layer is not specifically named Flock deployment areas')
    fields=layer.get('fields')
    oid_field=layer.get('objectIdField') or 'OBJECTID'
    if (not isinstance(fields,list) or not any(
        x.get('name')==oid_field and x.get('type')=='esriFieldTypeOID'
        for x in fields if isinstance(x,dict))):
        raise ValueError('Official polygon source has no persistent object identifier')

    base=url+'/query?'
    idquery=urllib.parse.urlencode({'where':'1=1','returnIdsOnly':'true','f':'json'})
    identities=government_gis_json(base+idquery).get('objectIds')
    if (not isinstance(identities,list) or not 1<=len(identities)<=MAX_POLYGONS
        or len(set(identities))!=len(identities)
        or any(type(x) is not int or x<=0 for x in identities)):
        raise ValueError('Original government GIS polygon ID list incomplete')
    query=urllib.parse.urlencode({
        'objectIds':','.join(str(x) for x in sorted(identities)),
        'outFields':oid_field,'returnGeometry':'true','outSR':4326,'f':'json'})
    response=government_gis_json(base+query)
    features=response.get('features')
    if (not isinstance(features,list) or len(features)!=len(identities)
        or response.get('exceededTransferLimit')):
        raise ValueError('Original government GIS polygon geometry truncated')
    if government_gis_json(base+idquery).get('objectIds')!=identities:
        raise ValueError('Original government polygon inventory changed during verification')

    outputs=[]
    seen=set()
    for feature in features:
        attr=feature.get('attributes') if isinstance(feature,dict) else None
        geom=feature.get('geometry') if isinstance(feature,dict) else None
        oid=attr.get(oid_field) if isinstance(attr,dict) else None
        rings=geom.get('rings') if isinstance(geom,dict) else None
        if type(oid) is not int or oid not in identities or oid in seen:
            raise ValueError('Source polygon identity ambiguous')
        seen.add(oid)
        if not isinstance(rings,list) or len(rings)!=1:
            raise ValueError('Multipart or hole-bearing polygon requires topology verification')
        ring=rings[0]
        if (not isinstance(ring,list) or not 4<=len(ring)<=250
            or ring[0]!=ring[-1]):
            raise ValueError('Original government polygon ring not closed')
        if not all(isinstance(pt,list) and len(pt)==2 and
                   all(type(n) in (float,int) for n in pt) and
                   -180<=pt[0]<=-64 and 17<=pt[1]<=72 for pt in ring):
            raise ValueError('Original government polygon coordinate invalid')
        digest=hashlib.sha256(json.dumps({
            'programme':prog['program_key'],'url':url,'oid':oid,'ring':ring
        },sort_keys=True,separators=(',',':')).encode()).hexdigest()
        outputs.append({
            'p_program_key':prog['program_key'],'p_layer_url':url,
            'p_area_key':'area_'+digest[:24],
            'p_area_label':f"Flock deployment area · {prog['jurisdiction_label']} #{oid}",
            'p_polygon_sha256':digest,'p_original_page_sha256':page_hash,
            'p_outline':ring,
        })
    return outputs


def run(dry_run=False):
    stats=Counter()
    pages=government_programmes()
    stats['government_programmes']=len(pages)
    for programme in pages:
        page=programme['official_evidence_url']
        try:
            if not gov_apex(page):
                continue
            doc,sha=fetch_government_page(page)
            stats['original_pages_checked']+=1
            for layer in direct_government_polygon_links(page,doc):
                try:
                    results=original_polygon_payloads(programme,layer,sha)
                    stats['verified_original_polygon_features']+=len(results)
                    for result in results:
                        if not dry_run:
                            ok=api_request('rpc/register_government_program_flock_area',
                              method='POST',payload=result)
                            if ok is not True:
                                raise ValueError('Original government polygon registration denied')
                            stats['new_or_rechecked_areas']+=1
                except Exception as e:
                    stats['government_polygon_layers_held']+=1
                    print('Original government polygon layer held:',
                          programme['program_key'],type(e).__name__,str(e)[:180])
        except Exception as e:
            stats['original_pages_held']+=1
            print('Original government polygon page unavailable:',
                  programme['program_key'],type(e).__name__,str(e)[:150])
    for key in ('government_programmes','original_pages_checked','original_pages_held',
                'verified_original_polygon_features','government_polygon_layers_held',
                'new_or_rechecked_areas'):
        print('Independent programme polygon',key+':',stats[key])
    print('Non-georeferenced programme descriptions converted into invented polygons: 0')
    if pages and not stats['original_pages_checked']:
        raise RuntimeError('Every original programme website unavailable; no polygon scan completed')
    return stats


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--dry-run',action='store_true')
    run(a.parse_args().dry_run)
