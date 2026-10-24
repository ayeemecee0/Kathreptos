"""Investigate first-party county GIS camera layers without requiring a camera backlink.

New provenance path: agency-published GIS server under the SAME verified
government registrable domain as an official agency GIS homepage. The domain
path proves who HOSTS the layer, not whether every pin is a Flock ALPR.
Requires GIS service listing, stable object IDs, Flock-specific point-layer
metadata and whole-source bounded API checks. Does not publish automatically.
"""
from collections import Counter
from urllib.parse import urlsplit, urlencode, urljoin
import hashlib
import json
import re

from discover_government_gis_links import fetch_government_page, normalized_url
from auto_verify_camera_gis import get_official_json
from government_domain_registry import public_dns
from discover_camera_gis_sources import stage_candidate

from first_party_registry import load_sources

SOURCES=load_sources()
MAX_ITEMS=250
FLOCK_NAME=re.compile(r'^flock[_ ]cameras(?: - [A-Za-z][A-Za-z ]{0,60})?$',re.I)
ID_FIELDS=('CameraID','Camera_ID','NAME','ID','CameraNo','CameraNumber')

def apex(host):
    if not host or len(host)>250 or not re.fullmatch(r'[a-z0-9.-]+',host):
        return None
    parts=host.split('.')
    if len(parts)<3 or any(not x for x in parts):
        return None
    return '.'.join(parts[-2:])

def authority(source,document):
    """Original agency site must control both hosted GIS server and portal."""
    root=urlsplit(source['original_gis_page'])
    gis=urlsplit(source['layer'])
    portal=urlsplit(source['public_gis_anchor'])
    domain=apex(root.hostname)
    if (root.scheme!='https' or gis.scheme!='https' or portal.scheme!='https'
        or domain is None or domain!=apex(gis.hostname) or domain!=apex(portal.hostname)
        or root.username or gis.username or portal.username or root.password
        or gis.password or portal.password or root.port or gis.port or portal.port
        or root.fragment or gis.fragment or gis.query or gis.fragment
        or not re.fullmatch(r'/[A-Za-z0-9_/-]+/(?:FeatureServer|MapServer)/[0-9]+',gis.path)):
        raise ValueError('No matched independent original-agency GIS hostname provenance')
    # Generic original GIS page proves agency publisher; a link to its own
    # map portal proves agency-operated GIS system. NO proof of Flock layer yet.
    expected=normalized_url(source['public_gis_anchor'])
    if not expected:
        raise ValueError('Expected original agency GIS portal URL is not a valid HTTPS URL')
    linked=set()
    for href,label in document.anchors:
        if isinstance(href,str):
            candidate=normalized_url(urljoin(source['original_gis_page'],href))
            if candidate:
                linked.add(candidate.rstrip('/'))
    if expected.rstrip('/') not in linked:
        raise ValueError('Live original-government GIS page does not link to agency mapping portal')
    return domain

def inspect(source,get_page=None,fetch=None,include_private_locations=False):
    # Resolve overridable transports on invocation: unit tests must never
    # accidentally use a default-bound live network function.
    get_page=get_page or fetch_government_page
    fetch=fetch or get_official_json
    if source not in SOURCES:
        raise ValueError('Only pinned independently sourced government GIS pages may be fetched')
    agency=urlsplit(source['original_gis_page']).hostname
    layer_host=urlsplit(source['layer']).hostname
    if not public_dns(agency) or not public_dns(layer_host):
        raise ValueError('Government host does not resolve publicly')
    original,checksum=get_page(source['original_gis_page'])
    authority(source,original)
    layer_url=source['layer']
    root=layer_url.rsplit('/',1)[0]
    service=fetch(root+'?f=json')
    meta=fetch(layer_url+'?f=json')
    if not isinstance(service,dict) or not isinstance(meta,dict):
        raise ValueError('Government GIS metadata unavailable')
    names=service.get('layers')
    layername=meta.get('name')
    oid=meta.get('objectIdField')
    fields=meta.get('fields')
    if (service.get('error') or meta.get('error') or
        not isinstance(layername,str) or not FLOCK_NAME.fullmatch(layername)
        or meta.get('geometryType')!='esriGeometryPoint' or meta.get('type')!='Feature Layer'
        or not isinstance(fields,list) or not 1<=len(fields)<=120
        or not isinstance(oid,str) or
        not any(isinstance(f,dict) and f.get('name')==oid and f.get('type')=='esriFieldTypeOID' for f in fields)
        or not isinstance(names,list) or
        not any(isinstance(x,dict) and x.get('id')==int(layer_url.rsplit('/',1)[1])
            and x.get('name')==layername for x in names)):
        raise ValueError('Agency map does not document complete exact Flock camera point-layer identity')
    ids=[f.get('name') for f in fields if isinstance(f,dict)]
    id_field=next((item for item in ID_FIELDS if item in ids),None)
    # First-party government datasets may identify individual features with
    # Esri's typed OBJECTID only. A second free-text CameraID field is NOT a
    # universal requirement. Require nonempty, unique typed OBJECTIDs from
    # two independent ArcGIS requests instead.
    if not id_field:
        id_field=oid
    # Verify complete original set via returnIdsOnly before requesting geometry.
    idresponse=fetch(layer_url+'/query?'+urlencode({
       'where':'1=1','returnIdsOnly':'true','f':'json'}))
    identities=idresponse.get('objectIds') if isinstance(idresponse,dict) else None
    if (not isinstance(identities,list) or
        not 1<=len(identities)<=MAX_ITEMS or
        len(set(identities))!=len(identities) or
        any(type(x)!=int or x<0 for x in identities)):
        raise ValueError('Government camera inventory missing, incomplete or too large for safe audit')
    result=fetch(layer_url+'/query?'+urlencode({
        'objectIds':','.join(map(str,sorted(identities))),'outFields':','.join(dict.fromkeys((oid,id_field))),
        'outSR':4326,'returnGeometry':'true','f':'json'
    }))
    entries=result.get('features') if isinstance(result,dict) else None
    if (not isinstance(entries,list) or len(entries)!=len(identities) or
       result.get('error') or result.get('exceededTransferLimit')):
        raise ValueError('Government camera GIS geometry missing or truncated')
    bounds=[source[k] for k in ('bounds_south','bounds_west','bounds_north','bounds_east')]
    points=[];seen=set()
    for feature in entries:
        attr=feature.get('attributes') if isinstance(feature,dict) else None
        geom=feature.get('geometry') if isinstance(feature,dict) else None
        if not isinstance(attr,dict) or not isinstance(geom,dict):
            raise ValueError('Camera GIS feature has no original identifying geometry')
        fid,individual=attr.get(oid),attr.get(id_field)
        lat,lon=geom.get('y'),geom.get('x')
        if (type(fid)!=int or fid not in identities or fid in seen or
            (id_field!=oid and (not isinstance(individual,str) or not 1<=len(individual.strip())<=100)) or
            type(lat) not in (int,float) or type(lon) not in (int,float) or
            not bounds[0]<=lat<=bounds[2] or
            not bounds[1]<=lon<=bounds[3]):
            raise ValueError('Incomplete or ambiguous agency Flock camera IDs/coordinates')
        seen.add(fid)
        points.append((fid,round(lat,7),round(lon,7)))
    # Re-fetch the authoritative ID inventory to detect edits midway
    # through an independent full-lane point query.
    confirmation=fetch(layer_url+'/query?'+urlencode({
       'where':'1=1','returnIdsOnly':'true','f':'json'}))
    if (not isinstance(confirmation,dict) or
        sorted(confirmation.get('objectIds') or [])!=sorted(identities) or
        confirmation.get('error')):
        raise ValueError('Government camera identifiers changed during GIS inspection')
    digest=hashlib.sha256(json.dumps(sorted(points),separators=(',',':')).encode()).hexdigest()
    proof={
       'layer_url':layer_url,
       'layer_name':layername,
       'object_id_field':oid,
       'individual_id_field':id_field,
       'identifier_basis':'arcgis_typed_objectid' if id_field==oid else 'named_camera_id',
       'original_page_sha256':checksum,
       'geometry_sha256':digest,
       'point_count':len(points),
       'jurisdiction':source['jurisdiction'],
       # Verified authority HOST/metadata, but operational status, recent
       # deployment and physical device confirmation remain separate questions.
       'status':'agency_host_identity_and_complete_layer_geometry_checked',
    }
    if include_private_locations:
        # In-memory only; never print, upload to GitHub artifacts, or cache.
        proof['_private_locations']=[{'id':oid,'lat':lat,'lon':lon} for oid,lat,lon in points]
    return proof

def run(dry_run=True):
    stats=Counter()
    for source in SOURCES:
        try:
            result=inspect(source)
            stats['qualified_original_agency_layers']+=1
            stats['complete_original_points']+=result['point_count']
            print('AGENCY GIS EVIDENCE PASS:',source['jurisdiction'],
                  'complete layer points',result['point_count'],
                  'independent government host',apex(urlsplit(source['layer']).hostname))
            if not dry_run:
                stage_candidate({
                  'gis_layer_url':result['layer_url'],
                  'layer_name':result['layer_name'],
                  'geometry_type':'esriGeometryPoint',
                  'object_id_field':result['object_id_field'],
                  'layer_purpose':(
                    'PRIVATE original-agency-hosted GIS lead. Agency GIS homepage, '
                    'same government domain, full source camera identifiers, exact '
                    'GIS service metadata and point inventory independently checked. '
                    'Physical deployment and current operation NOT established.'),
                  'public_gov_context_url':source['original_gis_page'],
                  'trust_status':'unverified'
                })
                stats['private_sources_staged']+=1
        except Exception as e:
            stats['held']+=1
            print('AGENCY GIS EVIDENCE HELD:',source['jurisdiction'],
                  type(e).__name__,str(e)[:180])
    print('AGENCY GIS FIRST-PARTY',dict(stats))
    print('Public camera locations promoted: 0 (publisher verification is separate from publication)')
    return stats

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage-private',action='store_true')
    args=ap.parse_args()
    result=run(dry_run=not args.stage_private)
    if result['held']:
        raise SystemExit('Agency-hosted GIS needs further independent evidence; no public camera published')
