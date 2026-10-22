"""Authorize government-ENDORSED but externally hosted ArcGIS Flock points.

An Esri organization label or Flock camera item title alone is NEVER proof of
municipal endorsement. A previously independently reviewed municipal source
must directly hyperlink the exact layer in a live Flock camera disclosure.
The worker separately fetches ArcGIS item and organization metadata, original
point schema and all camera geometry; database security-definer RPCs recheck
the original-government exact-link receipt and prevent duplicate publication.
Indeterminate evidence is held unpublished; no geocoding or inferred pins.
"""
import argparse
import hashlib
import json
import re
import urllib.parse
from collections import Counter
from urllib.error import HTTPError

from auto_verify_flock_agenda import api_request
from auto_verify_camera_gis import get_official_json
from auto_verify_camera_profiles import check_metadata, verify_points, sync as refresh_verified
from corroborate_candidate_government_links import direct_candidate_links
from discover_government_gis_links import fetch_government_page

LAYER_URL=re.compile(
 r"^https://services[0-9]*\.arcgis\.com/[A-Za-z0-9]+/"
 r"arcgis/rest/services/[A-Za-z0-9_-]+/FeatureServer/[0-9]+$")
FIELDS=("CameraType","Type","Manufacturer")
IDENTIFIERS=("CameraID","ID","NAME","Camera_ID")
MAX_FEATURES=250


def source_inputs():
    links=api_request("government_gis_disclosure_leads?select=disclosure_url,"
      "gis_layer_url,jurisdiction_label,discovery_method,government_page_sha256,"
      "layer_metadata_status&discovery_method=eq.government_page_direct_anchor_v1&limit=100")
    candidates=api_request("flock_gis_source_candidates?select=gis_layer_url,"
      "layer_name,geometry_type,object_id_field,trust_status"
      "&trust_status=eq.unverified&limit=130")
    sources=api_request("trusted_flock_gis_sources?select=source_key,gis_layer_url,"
      "government_evidence_url,jurisdiction_label,bounds_south,bounds_west,"
      "bounds_north,bounds_east,source_status&source_status=eq.verified&limit=100")
    roots=api_request("gis_government_host_authorities?select=authority_key,"
      "government_gis_host,official_government_page,allowed_layer_path,"
      "jurisdiction_label,verification_status&verification_status=eq.verified&limit=100")
    if not all(isinstance(x,list) and len(x)<n for x,n in (
        (links,100),(candidates,130),(sources,100),(roots,100))):
        raise ValueError("Trusted original-government hyperlink registry incomplete")
    candidate_by={x["gis_layer_url"]:x for x in candidates}
    root_by={x["authority_key"]:x for x in roots}
    for source in sources:
        root=root_by.get(source["source_key"])
        if not root:continue
        if (source["gis_layer_url"]!="https://"+root["government_gis_host"]+
                root["allowed_layer_path"] or
            source["government_evidence_url"]!=root["official_government_page"] or
            source["jurisdiction_label"]!=root["jurisdiction_label"]):
            raise ValueError("Originally verified agency/source binding changed")
        for link in links:
            url=link["gis_layer_url"]
            candidate=candidate_by.get(url)
            if (candidate and LAYER_URL.fullmatch(url) and
                link["disclosure_url"]==root["official_government_page"] and
                link["jurisdiction_label"]==root["jurisdiction_label"] and
                link["layer_metadata_status"] in ("unverified","point_layer_verified") and
                candidate["geometry_type"]=="esriGeometryPoint" and
                candidate["object_id_field"]=="OBJECTID"):
                yield source,root,link,candidate


def arcgis_original_org(service_url,jurisdiction):
    # Only ArcGIS-owned fixed search/portal endpoints, never arbitrary URLs
    # suggested by the candidate metadata.
    search="https://www.arcgis.com/sharing/rest/search?"+urllib.parse.urlencode({
      "f":"json","q":'type:"Feature Service" AND url:"'+service_url+'"',
      "num":30
    })
    response=get_official_json(search)
    items=response.get("results") if isinstance(response,dict) else None
    if not isinstance(items,list) or len(items)>30:
        raise ValueError("Original ArcGIS ownership item search unavailable")
    exact=[x for x in items if (isinstance(x,dict) and
          x.get("type")=="Feature Service" and x.get("url")==service_url)]
    if len(exact)!=1:
        raise ValueError("Original ArcGIS service is not uniquely attributable to an item")
    item=exact[0]
    org_id=item.get("orgId")
    owner=item.get("owner")
    if (not isinstance(org_id,str) or not re.fullmatch(r"[A-Za-z0-9]{8,48}",org_id)
        or not isinstance(owner,str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,90}",owner)):
        raise ValueError("ArcGIS organization or item owner not independently identified")
    portal=get_official_json("https://www.arcgis.com/sharing/rest/portals/"+
                            org_id+"?f=json")
    if not isinstance(portal,dict) or portal.get("id")!=org_id:
        raise ValueError("Original ArcGIS organization does not confirm its ID")
    name=portal.get("name")
    if (not isinstance(name,str) or not 5<=len(name)<=150 or
       jurisdiction.split(",",1)[0].lower() not in name.lower()):
        raise ValueError("ArcGIS organization is not independently named for this jurisdiction")
    return org_id,name


def source_payload(source,root,link,candidate):
    url=link["gis_layer_url"]
    if not LAYER_URL.fullmatch(url):
        raise ValueError("Not an eligible ArcGIS-owned public FeatureServer URL")
    doc,digest=fetch_government_page(link["disclosure_url"])
    evidence=direct_candidate_links(doc,link["disclosure_url"],digest,
        root["jurisdiction_label"],{url:candidate})
    if (len(evidence)!=1 or digest!=link["government_page_sha256"] or
        evidence[0]["gis_layer_url"]!=url):
        raise ValueError("Current original government Flock page no longer directly endorses exact layer")
    service_url=url.rsplit("/",1)[0]
    org_id,org_name=arcgis_original_org(service_url,root["jurisdiction_label"])
    service=get_official_json(service_url+"?f=json")
    layer=get_official_json(url+"?f=json")
    cols={f.get("name") for f in layer.get("fields",[]) if isinstance(f,dict)}
    identity=next((c for c in IDENTIFIERS if c in cols),None)
    vendor=next((c for c in FIELDS if c in cols),None)
    if not identity:
        raise ValueError("ArcGIS original camera ID field absent")
    temp_policy={
      "identity_mode":"official_flock_layer",
      "expected_layer_name":candidate["layer_name"],
      "camera_id_field":identity,
      "vendor_field":vendor,
      "service_evidence_mode":"listed_flock_layer",
    }
    if not re.fullmatch(r"flock[_ ]cameras(?: - [A-Za-z][A-Za-z ]{0,60})?",
                        candidate["layer_name"],re.I):
        raise ValueError("ArcGIS metadata does not independently identify Flock cameras")
    temp_source={**source,"gis_layer_url":url,"expected_id_field":"OBJECTID"}
    check_metadata(temp_source,temp_policy,service,layer)
    query=urllib.parse.urlencode({
      "where":"1=1",
      "outFields":",".join(sorted({"OBJECTID",identity}|({vendor} if vendor else set()))),
      "returnGeometry":"true","outSR":"4326","resultRecordCount":MAX_FEATURES+1,
      "orderByFields":"OBJECTID ASC","f":"json"
    })
    rows=get_official_json(url+"/query?"+query)
    features=rows.get("features") if isinstance(rows,dict) else None
    if (not isinstance(features,list) or not 1<=len(features)<=MAX_FEATURES
        or rows.get("error") or rows.get("exceededTransferLimit")):
        raise ValueError("Original candidate GIS data incomplete or ambiguous")
    records,held,n=verify_points(temp_source,temp_policy,rows)
    if held or len(records)!=n:
        raise ValueError("Original source has non-Flock or ambiguous camera features; no partial publication")
    # Original per-layer OBJECTID is the mandatory stable evidence identity.
    # Use original feature IDs, not inferred coordinates or labels.
    locs=[]
    for entry in features:
        att=entry["attributes"]
        locs.append({
          "id":att["OBJECTID"],
          "lat":round(entry["geometry"]["y"],7),
          "lon":round(entry["geometry"]["x"],7),
        })
    digest_layer=hashlib.sha256(json.dumps({
       "url":url,"layer":layer["name"],"org":org_id,
       "locations":locs
    },sort_keys=True,separators=(",",":")).encode()).hexdigest()
    key="ext_"+hashlib.sha256((source["source_key"]+url).encode()).hexdigest()[:24]
    return {
      "p_parent_source_key":source["source_key"],
      "p_source_key":key,
      "p_disclosure_url":link["disclosure_url"],
      "p_gis_layer_url":url,
      "p_layer_name":layer["name"],
      "p_camera_id_field":identity,
      "p_vendor_field":vendor,
      "p_page_sha256":digest,
      "p_layer_sha256":digest_layer,
      "p_org_id":org_id,
      "p_org_title":org_name,
      "p_locations":locs,
    }


def run(dry_run=False):
    counts=Counter();seen=set()
    for source,root,link,candidate in source_inputs():
        url=link["gis_layer_url"]
        if url in seen:continue
        seen.add(url)
        try:
            args=source_payload(source,root,link,candidate)
            counts["independently_qualified"]+=1
            print("Verified government-endorsed external ArcGIS Flock layer:",
                  root["jurisdiction_label"],url,"cameras",len(args["p_locations"]))
            if dry_run:continue
            proof={k:args[k] for k in (
              "p_parent_source_key","p_disclosure_url","p_gis_layer_url","p_page_sha256"
            )}
            confirmed=api_request("rpc/confirm_original_government_linked_point_layer",
                method="POST",payload={
                  "p_parent_source_key":proof["p_parent_source_key"],
                  "p_disclosure_url":proof["p_disclosure_url"],
                  "p_layer_url":proof["p_gis_layer_url"],
                  "p_page_sha256":proof["p_page_sha256"],
                })
            if confirmed is not True:
                raise ValueError("Government source attestation refused")
            accepted=api_request("rpc/register_official_external_flock_gis",
                method="POST",payload=args)
            if accepted is not True:
                raise ValueError("Original-government ArcGIS publisher registration refused")
            counts["registered"]+=1
        except HTTPError as exc:
            reason=exc.read(1200).decode("utf8","replace")
            counts["held"]+=1
            if not ("Potential duplicate already verified camera" in reason):
                counts["unexpected_errors"]+=1
            print("Government-endorsed GIS registration refused:",
                  url,"HTTP",exc.code,reason[:400])
        except ValueError as exc:
            counts["held"]+=1
            print("External source withheld:",url,str(exc)[:250])
        except Exception as exc:
            counts["held"]+=1;counts["unexpected_errors"]+=1
            print("Unexpected external GIS source verifier error:",
                  url,type(exc).__name__,str(exc)[:220])
    if counts["registered"] and not dry_run:
        refreshed=refresh_verified()
        counts["published_camera_points"]=refreshed["published"]
        if refreshed["errors"]:
            counts["unexpected_errors"]+=refreshed["errors"]
            print("External GIS source registered but publication recheck failed",
                  refreshed["errors"])
    for key in ("independently_qualified","registered","published_camera_points",
                "held","unexpected_errors"):
        print("External government GIS",key+":",counts[key])
    print("Flock points directly published from unreviewed Esri organization names: 0")
    return counts


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    results=run(a.parse_args().dry_run)
    if results["unexpected_errors"]:
        raise SystemExit("Unexpected external government GIS registration failure")
