"""Scan owner-verified municipal ArcGIS service catalogs for Flock layers.

Unlike a hardcoded list of GIS layer numbers, this enumerates folders and
MapServer/FeatureServer services on an authority-bound government GIS host.
Potential Flock camera point layers are staged privately. They NEVER become
new owner-reviewed trust roots, source verification profiles or public pins.
"""
import argparse
import datetime as dt
import re
import urllib.parse
from collections import Counter

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from auto_verify_camera_gis import get_official_json
from discover_camera_gis_sources import stage_candidate

FLOCK=re.compile(r'^flock[_ -]*cameras?$',re.I)
SERVICE_NAME=re.compile(r'^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?$')
FOLDER_NAME=re.compile(r'^[A-Za-z0-9_-]{1,90}$')
MAX_FOLDERS=35
# Large city GIS catalogs are scanned in 32-service daily slices; rejecting
# the entire catalog because it exceeds 240 services hides valid sources.
MAX_SERVICES=2500
PER_DAY=32


def verified_roots():
    rows=fetch_all(api_request,"gis_government_host_authorities?select=authority_key,"
       "government_gis_host,official_government_page,allowed_layer_path,"
       "jurisdiction_label,verification_status"
       "&verification_status=eq.verified&limit=100","authority_key")
    return rows


def owner_prefix(root):
    if root.get("verification_status")!="verified":
        raise ValueError("No reviewed government GIS host")
    host=root.get("government_gis_host","")
    path=root.get("allowed_layer_path","")
    if not re.fullmatch(r'[a-z0-9.-]+',host):
        raise ValueError("Unsafe authority host")
    # Only the exact REST directory ancestor of the already reviewed layer is
    # allowed to be crawled. No untrusted discovered host is ever followed.
    m=re.match(r'^(.+/rest/services)/[A-Za-z0-9_/-]+/(?:MapServer|FeatureServer)/\d+$',path)
    if not m:
        raise ValueError("Source authority path not an ArcGIS REST server")
    return "https://"+host+m.group(1)


def catalog_services(root):
    prefix=owner_prefix(root)
    listing=get_official_json(prefix+"?f=json")
    folders=listing.get("folders")
    services=listing.get("services")
    if not isinstance(folders,list) or not isinstance(services,list) or len(folders)>MAX_FOLDERS:
        raise ValueError("Original ArcGIS service catalog malformed or oversized")
    seen={}
    def add(rows):
        for svc in rows:
            if not isinstance(svc,dict):continue
            name,kind=svc.get("name"),svc.get("type")
            if kind not in ("MapServer","FeatureServer") or not isinstance(name,str):
                continue
            if not SERVICE_NAME.fullmatch(name):continue
            url=prefix+"/"+name+"/"+kind
            seen[url]=url
    add(services)
    for name in folders:
        if not isinstance(name,str) or not FOLDER_NAME.fullmatch(name):
            continue
        entries=get_official_json(prefix+"/"+name+"?f=json")
        if isinstance(entries,dict) and isinstance(entries.get("services"),list):
            add(entries["services"])
    if len(seen)>MAX_SERVICES:
        raise ValueError("Government GIS catalog too broad to be checked reliably")
    return sorted(seen)


def candidates_from_service(root,service_url,meta):
    if not isinstance(meta,dict) or meta.get("error"):
        raise ValueError("Government ArcGIS metadata unavailable")
    rows=meta.get("layers")
    if not isinstance(rows,list) or len(rows)>300:
        raise ValueError("ArcGIS catalog layers unavailable or truncated")
    choices=[]
    for item in rows:
        name=item.get("name") if isinstance(item,dict) else None
        identity=item.get("id") if isinstance(item,dict) else None
        if not isinstance(name,str) or not FLOCK.fullmatch(name) or type(identity) is not int:
            continue
        choices.append((identity,name))
    return choices


def qualify_layer(root,service_url,identity,name,metadata):
    if (not isinstance(metadata,dict) or metadata.get("error") or
        metadata.get("name")!=name or metadata.get("type")!="Feature Layer" or
        metadata.get("geometryType")!="esriGeometryPoint"):
        return None
    fields=metadata.get("fields")
    if not isinstance(fields,list) or len(fields)>140:
        return None
    id_field=metadata.get("objectIdField") or "OBJECTID"
    if not any(isinstance(f,dict) and f.get("name")==id_field and
               f.get("type")=="esriFieldTypeOID" for f in fields):
        return None
    return {
      "gis_layer_url":service_url+"/"+str(identity),
      "layer_name":name,
      "geometry_type":"esriGeometryPoint",
      "object_id_field":id_field,
      "layer_purpose":(
        "Government-hosted map catalog advertises a Flock Cameras point layer. "
        "This is a PRIVATE discovery lead, not verification of installed "
        "ALPR equipment, individual coordinates or current operation."),
      "public_gov_context_url":root["official_government_page"],
      "trust_status":"unverified",
    }


def scan(dry_run=False,day=None):
    counts=Counter()
    day=(day if day is not None else dt.date.today().toordinal())
    for root in verified_roots():
        try:
            catalog=catalog_services(root)
            counts["catalog_services_total"]+=len(catalog)
            if not catalog:continue
            pages=(len(catalog)+PER_DAY-1)//PER_DAY
            batch=catalog[(day%pages)*PER_DAY:((day%pages)+1)*PER_DAY]
            for url in batch:
                try:
                    meta=get_official_json(url+"?f=json")
                    counts["service_metadata_checked"]+=1
                    for layerid,name in candidates_from_service(root,url,meta):
                        layer=get_official_json(url+"/"+str(layerid)+"?f=json")
                        candidate=qualify_layer(root,url,layerid,name,layer)
                        if not candidate:continue
                        counts["flock_layer_candidates"]+=1
                        if not dry_run:
                            stage_candidate(candidate)
                            counts["private_submissions"]+=1
                except Exception as exc:
                    counts["services_held"]+=1
                    print("Government GIS service held:",root["authority_key"],
                          type(exc).__name__,str(exc)[:140])
            counts["approved_hosts_checked"]+=1
            print("Government GIS catalog:",root["authority_key"],
                  "total services",len(catalog),"sampled",len(batch))
        except Exception as exc:
            counts["host_errors"]+=1
            print("Government GIS catalog host error:",root.get("authority_key"),
                  type(exc).__name__,str(exc)[:170])
    for k in ("approved_hosts_checked","catalog_services_total",
              "service_metadata_checked","flock_layer_candidates",
              "private_submissions","services_held","host_errors"):
        print("GIS catalog",k+":",counts[k])
    print("New publicly verified Flock camera pins from catalog alone: 0")
    return counts


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    result=scan(a.parse_args().dry_run)
    if result["host_errors"] or not result["approved_hosts_checked"]:
        raise SystemExit("Government-owned ArcGIS service catalog discovery incomplete")
