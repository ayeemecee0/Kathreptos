"""Discover Flock-labelled ArcGIS Online feature layers (PRIVATE leads ONLY).

The public ArcGIS item-search API is used for *discovery*, never as proof of
a government camera. Only static Esri-controlled feature-service hosts are
fetched; never follow a user-supplied URL, redirect, or shared map blindly.
Newly found layers require an original government disclosure and an independent
source authority before publication. No public camera table is ever touched.
"""
import argparse
from collections import Counter
import re
import urllib.parse

from auto_verify_camera_gis import get_official_json
from discover_camera_gis_sources import stage_candidate

SEARCH_ENDPOINT="https://www.arcgis.com/sharing/rest/search"
QUERIES=(
    'title:"Flock Cameras" AND type:"Feature Service"',
    'title:"Flock Camera" AND type:"Feature Service"',
    'tags:"Flock Safety" AND type:"Feature Service"',
)
SERVICE_URL=re.compile(
    r'^https://services[0-9]*\.arcgis\.com/[A-Za-z0-9]+/'
    r'(?:[Aa]rc[Gg][Ii][Ss]/rest/services|arcgis/rest/services)/'
    r'[A-Za-z0-9_-]+/FeatureServer$')
FLOCK=re.compile(r'\bflock\b',re.I)
CAMERA=re.compile(r'\bcameras?\b',re.I)
MAX_SEARCH=40
MAX_SERVICES=48
MAX_LAYERS=8


def public_search(query):
    url=SEARCH_ENDPOINT+"?"+urllib.parse.urlencode({
      "q":query,"f":"json","num":MAX_SEARCH,"start":1,
      "sortField":"modified","sortOrder":"desc",
    })
    obj=get_official_json(url)
    results=obj.get("results") if isinstance(obj,dict) else None
    if not isinstance(results,list) or len(results)>MAX_SEARCH:
        raise ValueError("Public ArcGIS catalog search is incomplete or malformed")
    return results


def vetted_service_url(item):
    if not isinstance(item,dict) or item.get("type")!="Feature Service":
        return None
    title=item.get("title","")
    url=item.get("url","")
    if not isinstance(title,str) or not isinstance(url,str):
        return None
    if not FLOCK.search(title) and not FLOCK.search(" ".join(item.get("tags") or [])):
        return None
    if not SERVICE_URL.fullmatch(url):
        return None
    return url


def valid_candidate(layer_url,detail):
    if not isinstance(detail,dict) or detail.get("error"):
        return None
    name=detail.get("name")
    if (not isinstance(name,str) or len(name)>180 or
        not FLOCK.search(name) or not CAMERA.search(name) or
        detail.get("type")!="Feature Layer" or
        detail.get("geometryType")!="esriGeometryPoint"):
        return None
    fields=detail.get("fields")
    oid=detail.get("objectIdField")
    if (not isinstance(fields,list) or len(fields)>120 or
        not isinstance(oid,str) or not any(
        isinstance(f,dict) and f.get("name")==oid and f.get("type")=="esriFieldTypeOID"
        for f in fields)):
        return None
    return {
      "gis_layer_url":layer_url,
      "layer_name":name,
      "geometry_type":"esriGeometryPoint",
      "object_id_field":oid,
      "layer_purpose":(
        "PUBLIC ESRI CATALOG DISCOVERY ONLY: The layer name mentions Flock cameras. "
        "ArcGIS ownership, original government affiliation, equipment type, "
        "individual position and operational status are NOT verified. "
        "This remains private until independent original-agency evidence."),
      "public_gov_context_url":None,
      "trust_status":"unverified",
    }


def scan(dry_run=False):
    stats=Counter()
    candidate_services={}
    for q in QUERIES:
        try:
            items=public_search(q)
            stats["queries_succeeded"]+=1
            for item in items:
                url=vetted_service_url(item)
                if url: candidate_services[url]=item
        except Exception as err:
            stats["search_errors"]+=1
            print("ArcGIS public item search unavailable:",type(err).__name__,str(err)[:140])
    if not stats["queries_succeeded"]:
        raise ValueError("No valid ArcGIS public catalog responses")
    stats["catalog_services_found"]=len(candidate_services)
    if len(candidate_services)>MAX_SERVICES:
        raise ValueError("Public GIS catalog source sample is too large; narrow search")
    known=set()
    for url in candidate_services:
        try:
            service=get_official_json(url+"?f=json")
            layers=service.get("layers") if isinstance(service,dict) else None
            if not isinstance(layers,list) or len(layers)>100:
                raise ValueError("No feature service layer list")
            stats["services_checked"]+=1
            for layer in layers[:MAX_LAYERS]:
                if not isinstance(layer,dict):continue
                layer_id=layer.get("id")
                if type(layer_id) is not int or layer_id<0 or layer_id>999:continue
                name=layer.get("name")
                if not isinstance(name,str) or not FLOCK.search(name) or not CAMERA.search(name):
                    continue
                layer_url=url+"/"+str(layer_id)
                if layer_url in known:continue
                known.add(layer_url)
                candidate=valid_candidate(layer_url,get_official_json(layer_url+"?f=json"))
                if not candidate:continue
                stats["qualified_private_leads"]+=1
                if not dry_run:
                    stage_candidate(candidate);stats["staged"]+=1
        except Exception as err:
            stats["services_held"]+=1
            print("ArcGIS public item held:",type(err).__name__,str(err)[:140])
    for k in ("queries_succeeded","search_errors","catalog_services_found",
              "services_checked","qualified_private_leads","staged","services_held"):
        print("Global ArcGIS Flock discovery",k+":",stats[k])
    print("Government camera sources verified from ArcGIS search results: 0")
    print("Public camera pins created from ArcGIS search results: 0")
    return stats


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    scan(a.parse_args().dry_run)
