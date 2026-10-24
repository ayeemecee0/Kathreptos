"""Classify the *private* government-GIS verification backlog without promoting pins.

A Flock-looking ArcGIS name is not authority. Only originally approved hosts
may be queried for geometry. Compare their complete point inventories against
already verified original-government points to isolate possible duplicate
datasets from genuinely new coverage. Never print candidate URLs/coordinates.
"""
import collections
import hashlib
import math
import re
from urllib.parse import urlsplit

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from auto_register_derived_gis import discovery_inputs, verify_layer

CANDIDATE_LIMIT=150
MAX_POINTS=5000
EXTERNAL_ESRI=re.compile(r'^services[0-9]*\.arcgis\.com$')
# Conservative possible-overlap hold. This does NOT establish physical
# camera identity; a human can later resolve nearby distinct devices.
NEAR_METERS=100

def host(url):
    if not isinstance(url,str) or len(url)>1500:return None
    try:
        p=urlsplit(url)
        if (p.scheme!='https' or not p.hostname or p.username or p.password
            or p.port is not None or p.query or p.fragment):
            return None
        return p.hostname.lower()
    except ValueError:
        return None

def original_domain(url):
    h=host(url)
    if not h:return None
    parts=h.split('.')
    if len(parts)<2:return None
    return '.'.join(parts[-2:])

def near(x,y):
    # x and y are (latitude,longitude) pairs. No route/user position data.
    lat1,lon1=x
    lat2,lon2=y
    if not all(type(n) in (int,float) and math.isfinite(n)
               for n in (lat1,lon1,lat2,lon2)):
        raise ValueError('Nonfinite original camera geometry in triage')
    return math.hypot((lat1-lat2)*111320,
        (lon1-lon2)*111320*math.cos(math.radians((lat1+lat2)/2)))<NEAR_METERS

def classify(candidate,verified_urls,verified_hosts,eligible,canonical,
             check=verify_layer):
    url=candidate.get('gis_layer_url')
    if not host(url):
        return ('unsafe_or_invalid_source_url',0,0)
    if url in verified_urls:
        return ('already_authorized_source_candidate_duplicate',0,0)
    matching=eligible.get(url)
    if matching:
        parent,root,exact=matching
        try:
            checked=check(parent,root,exact)
            locations=checked['p_locations']
            if not isinstance(locations,list) or not 1<=len(locations)<=300:
                raise ValueError('Original hosted GIS inventory missing or unbounded')
            existing=[(r['latitude'],r['longitude']) for r in canonical
                      if r.get('jurisdiction_label')==parent['jurisdiction_label']]
            overlapping=0
            for loc in locations:
                if any(near((loc['lat'],loc['lon']),point) for point in existing):
                    overlapping+=1
            if overlapping==len(locations):
                return ('trusted_host_all_points_possible_overlaps_hold',len(locations),overlapping)
            if overlapping:
                return ('trusted_host_mixed_new_and_possible_overlaps_hold',len(locations),overlapping)
            return ('trusted_host_distinct_points_eligible_for_existing_registration',len(locations),0)
        except Exception:
            # Do not leak service responses, hostname details, or coordinates.
            return ('trusted_host_original_metadata_or_inventory_held',0,0)
    if host(url) in verified_hosts:
        return ('trusted_host_layer_fails_inherited_evidence_policy',0,0)
    if EXTERNAL_ESRI.fullmatch(host(url)):
        return ('external_arcgis_needs_original_agency_endorsement',0,0)
    context=candidate.get('public_gov_context_url')
    if (context and original_domain(url) and
       original_domain(url)==original_domain(context)):
        return ('same_agency_domain_needs_publisher_review',0,0)
    return ('unattributed_gis_source_needs_original_agency_proof',0,0)

def inputs():
    candidates=fetch_all(api_request,
        'flock_gis_source_candidates?select=gis_layer_url,layer_name,'
        'geometry_type,object_id_field,trust_status,public_gov_context_url'
        '&trust_status=eq.unverified&limit=100',
        'gis_layer_url',max_records=CANDIDATE_LIMIT)
    trusted=fetch_all(api_request,
        'trusted_flock_gis_sources?select=source_key,gis_layer_url,'
        'jurisdiction_label,source_status&source_status=eq.verified&limit=100',
        'source_key',max_records=500)
    roots=fetch_all(api_request,
        'gis_government_host_authorities?select=authority_key,government_gis_host,'
        'verification_status&verification_status=eq.verified&limit=100',
        'authority_key',max_records=500)
    points=fetch_all(api_request,
        'flock_camera_locations?select=record_key,jurisdiction_label,latitude,longitude,'
        'verification_status,location_accuracy'
        '&verification_status=eq.verified&location_accuracy=eq.exact&limit=100',
        'record_key',max_records=MAX_POINTS)
    reviewed=fetch_all(api_request,
        'reviewed_first_party_gis_roots?select=source_key,gis_layer_url,review_status'
        '&review_status=eq.verified&limit=100',
        'source_key',max_records=500)
    if len(points)<293:
        raise ValueError('Public camera base lost verified records; refuse false triage')
    if not candidates:
        return candidates,trusted,roots,points,reviewed
    return candidates,trusted,roots,points,reviewed

def run():
    candidates,trusted,roots,points,reviewed=inputs()
    verified_urls={row['gis_layer_url'] for row in trusted}
    verified_hosts={row['government_gis_host'] for row in roots}
    approved_urls={row['gis_layer_url'] for row in reviewed}
    # Critically, this is *not* a self-authorizing list: it only helps
    # diagnose exactly reviewed candidate sources.
    matches={}
    for parent,root,candidate in discovery_inputs():
        url=candidate['gis_layer_url']
        if url not in matches:
            matches[url]=(parent,root,candidate)
    categories=collections.Counter()
    total_features=0
    possible_overlaps=0
    for candidate in sorted(candidates,key=lambda c:c['gis_layer_url']):
        url=candidate['gis_layer_url']
        kind,total,overlap=classify(candidate,verified_urls,verified_hosts,
                                    matches,points)
        categories[kind]+=1
        total_features+=total
        possible_overlaps+=overlap
        # Private research URLs are never logged; short stable IDs suffice
        # to deduplicate follow-up investigations in the repo workflows.
        marker=hashlib.sha256(url.encode()).hexdigest()[:12]
        print('GIS TRIAGE',kind,marker,'features',total,
              'possible_existing_nearby',overlap)
    for key in sorted(categories):
        print('GIS TRIAGE SUMMARY',key,categories[key])
    print('GIS TRIAGE ORIGINAL POINT FEATURES EXAMINED',total_features)
    print('GIS TRIAGE POSSIBLY OVERLAPPING EXISTING CAMERA RECORDS',possible_overlaps)
    print('GIS TRIAGE OWNER-REVIEWED GOVERNMENT SOURCE ROOTS',len(approved_urls))
    print('GIS TRIAGE NEW PUBLIC CAMERA LOCATIONS 0')
    print('GIS TRIAGE PRIVATE CANDIDATES RETAINED',len(candidates))
    return categories

if __name__=='__main__':
    run()
