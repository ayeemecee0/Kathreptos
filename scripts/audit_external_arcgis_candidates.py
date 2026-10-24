"""Read-only diagnostic for private externally hosted Flock GIS candidates.

Live ArcGIS metadata can reject malformed or withdrawn candidate layers, but it
CANNOT establish government ownership. Only a fresh, independently vetted
government disclosure can feed the existing external source attestation path.
Does not fetch/publish camera point coordinates or create trust.
"""
import argparse
from collections import Counter
import hashlib
import re
import urllib.parse

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from auto_verify_camera_gis import get_official_json
from auto_attest_external_arcgis import LAYER_URL

MAX_CANDIDATES=130


def candidate_inputs():
    candidates=fetch_all(api_request,
       "flock_gis_source_candidates?select=gis_layer_url,layer_name,"
       "geometry_type,object_id_field,trust_status"
       "&trust_status=eq.unverified&limit=130","gis_layer_url",
       max_records=MAX_CANDIDATES)
    links=fetch_all(api_request,
       "government_gis_disclosure_leads?select=gis_layer_url,"
       "discovery_method,layer_metadata_status&limit=100",
       "gis_layer_url,disclosure_url",max_records=5000)
    sources=fetch_all(api_request,
       "trusted_flock_gis_sources?select=gis_layer_url,source_status"
       "&source_status=eq.verified&limit=100","gis_layer_url",
       max_records=500)
    return candidates,links,sources


def check_external(candidate,links,verified):
    url=candidate["gis_layer_url"]
    if url in verified:
        return "already_trusted_layer_review_duplicate"
    if not LAYER_URL.fullmatch(url):
        return "not_external_arcgis"
    # Require the live original service to list the exact ID and name.
    service_url=url.rsplit("/",1)[0]
    layer=get_official_json(url+"?f=json")
    service=get_official_json(service_url+"?f=json")
    if not isinstance(layer,dict) or not isinstance(service,dict):
        return "metadata_unavailable"
    if layer.get("error") or service.get("error"):
        return "metadata_unavailable"
    fields=layer.get("fields")
    expected_id=candidate.get("object_id_field")
    oid=layer.get("objectIdField")
    if (layer.get("type")!="Feature Layer" or
        layer.get("geometryType")!="esriGeometryPoint" or
        layer.get("name")!=candidate.get("layer_name") or
        expected_id!=oid or not isinstance(fields,list) or
        not any(f.get("name")==oid and f.get("type")=="esriFieldTypeOID"
                for f in fields if isinstance(f,dict))):
        return "metadata_changed_or_not_point_camera_layer"
    layers=service.get("layers")
    layer_id=int(url.rsplit("/",1)[1])
    if (not isinstance(layers,list) or
        not any(isinstance(item,dict) and item.get("id")==layer_id and
                item.get("name")==candidate.get("layer_name") for item in layers)):
        return "service_does_not_list_exact_layer"
    if url not in links:
        return "verified_arcgis_metadata_only_missing_original_government_link"
    # Even a government-page receipt requires independent parent authority,
    # live original-page fingerprint, service metadata, feature identity and
    # duplication checks in auto_attest_external_arcgis.py before publication.
    return "candidate_government_link_needs_full_attestation"



# ArcGIS organization metadata identifies the publisher of a hosted layer,
# but the organization *name itself* is user-editable self-description. It
# can rank an investigation, NEVER approve a government source or locations.
def inspect_arcgis_publisher(layer_url,fetch=None):
    fetch=fetch or get_official_json
    if not LAYER_URL.fullmatch(layer_url):
        raise ValueError('Only an exact ArcGIS-hosted Flock layer may be inspected')
    service=layer_url.rsplit('/',1)[0]
    lookup='https://www.arcgis.com/sharing/rest/search?'+urllib.parse.urlencode({
        'f':'json','q':'type:"Feature Service" AND url:"'+service+'"','num':30
    })
    listing=fetch(lookup)
    matches=listing.get('results') if isinstance(listing,dict) else None
    if not isinstance(matches,list) or len(matches)>30:
        return 'unresolved_arcgis_item_search'
    # A coincidentally matching ArcGIS title is not a service-item identity.
    exact=[row for row in matches if isinstance(row,dict)
           and row.get('type')=='Feature Service' and row.get('url')==service]
    if len(exact)!=1:
        return 'arcgis_item_not_uniquely_attributed'
    item=exact[0]
    orgid=item.get('orgId')
    owner=item.get('owner')
    if not isinstance(orgid,str) or not re.fullmatch(r'[A-Za-z0-9]{8,48}',orgid):
        return 'arcgis_item_orgid_missing'
    if not isinstance(owner,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,90}',owner):
        return 'arcgis_item_owner_missing'
    # The portal may state a city, agency or nonprofit. That text is NOT a
    # link from a reviewed original .gov agency and conveys no public trust.
    portal=fetch('https://www.arcgis.com/sharing/rest/portals/'+orgid+'?f=json')
    if not isinstance(portal,dict) or portal.get('id')!=orgid:
        return 'arcgis_owner_portal_unavailable'
    name=portal.get('name')
    if not isinstance(name,str) or not 4<=len(name)<=200:
        return 'arcgis_org_self_description_missing'
    return 'arcgis_org_publisher_metadata_identified_not_government_verified'


def run():
    candidates,receipts,sources=candidate_inputs()
    links={x["gis_layer_url"] for x in receipts
           if x.get("discovery_method") in (
               "government_page_direct_anchor_v1",
               "government_page_direct_service_v1")}
    verified={x["gis_layer_url"] for x in sources}
    stats=Counter()
    for candidate in candidates:
        url=candidate["gis_layer_url"]
        if not LAYER_URL.fullmatch(url):
            continue
        stats["external_candidates"]+=1
        # Logs of a public repository must not disclose unpublished research URLs.
        candidate_id=hashlib.sha256(url.encode("utf8")).hexdigest()[:12]
        try:
            outcome=check_external(candidate,links,verified)
        except Exception as exc:
            outcome="unreachable_or_unparseable_metadata"
            print("ArcGIS candidate metadata held:",candidate_id,
                  type(exc).__name__)
        stats[outcome]+=1
        print("Private ArcGIS source audit:",outcome,candidate_id)
        if outcome=="verified_arcgis_metadata_only_missing_original_government_link":
            try:
                owner_state=inspect_arcgis_publisher(url)
            except Exception as exc:
                owner_state="arcgis_owner_lookup_unavailable"
                print("ArcGIS original owner lookup held:",candidate_id,type(exc).__name__)
            stats[owner_state]+=1
            print("ArcGIS owner provenance:",owner_state,candidate_id)
    for key in sorted(stats):
        print("External candidate audit",key+":",stats[key])
    print("ArcGIS organization self-description is NOT original-government endorsement")
    print("Government camera authorities newly established by this audit: 0")
    print("Camera locations published by this audit: 0")
    return stats


if __name__=="__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
