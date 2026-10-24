"""Safely auto-verify extra Flock camera GIS point layers on APPROVED government hosts.

The underlying city/county GIS host must already have an independently
reviewed and currently verified source. This DOES NOT approve ArcGIS Online
or any unverified third-party hosting organization. Source creation is through
a restrictive database RPC which independently checks the candidate, parent
host, reviewed profile, bounds and possible camera duplication.

If a government layer overlaps published cameras, withhold the entire source.
No synthetic camera points, public uploads, plate reads or arbitrary URL fetches.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.parse
from collections import Counter
from urllib.error import HTTPError

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from auto_verify_camera_gis import get_official_json
from auto_verify_camera_profiles import sync as refresh_verified

FIELDS=("NAME","CameraID","ID","Camera_ID")
LAYER_NAME=re.compile(r"^flock[_ ]cameras( - [A-Za-z][A-Za-z ]{0,60})?$",re.I)
MAX_INVENTORY=300


def discovery_inputs():
    parents=fetch_all(api_request,"trusted_flock_gis_sources?select=source_key,gis_layer_url,"
      "government_evidence_url,jurisdiction_label,bounds_south,bounds_west,"
      "bounds_north,bounds_east,source_status&source_status=eq.verified&limit=100","source_key")
    roots=fetch_all(api_request,"gis_government_host_authorities?select=authority_key,"
      "government_gis_host,official_government_page,allowed_layer_path,"
      "jurisdiction_label,verification_status&verification_status=eq.verified&limit=100","authority_key")
    candidates=fetch_all(api_request,"flock_gis_source_candidates?select=gis_layer_url,"
      "layer_name,geometry_type,object_id_field,trust_status"
      "&trust_status=eq.unverified&limit=130","gis_layer_url")
    root_by={r["authority_key"]:r for r in roots}
    for parent in parents:
        root=root_by.get(parent["source_key"])
        if not root: continue # Legacy vendor-specific source, not an inherited host.
        if (parent["gis_layer_url"]!="https://"+root["government_gis_host"]+
                root["allowed_layer_path"] or
            parent["government_evidence_url"]!=root["official_government_page"] or
            parent["jurisdiction_label"]!=root["jurisdiction_label"]):
            raise ValueError("Government owner root/source no longer matches")
        base="https://"+root["government_gis_host"]
        for candidate in candidates:
            url=candidate["gis_layer_url"]
            if (url.startswith(base+"/") and
                url!=parent["gis_layer_url"] and
                candidate["geometry_type"]=="esriGeometryPoint" and
                candidate["object_id_field"]=="OBJECTID" and
                LAYER_NAME.fullmatch(candidate["layer_name"])):
                yield parent,root,candidate


def verify_layer(parent,root,candidate):
    url=candidate["gis_layer_url"]
    p=urllib.parse.urlsplit(url)
    host=root["government_gis_host"]
    if (p.scheme!="https" or p.hostname!=host or p.username or p.password or
        p.port is not None or p.query or p.fragment or
        not re.fullmatch(r"/[A-Za-z0-9_/-]+/(MapServer|FeatureServer)/[0-9]+",p.path)):
        raise ValueError("Not an exact government-hosted GIS layer")
    base=url.rsplit("/",1)[0]
    service=get_official_json(base+"?f=json")
    layer=get_official_json(url+"?f=json")
    if not isinstance(service,dict) or not isinstance(layer,dict):
        raise ValueError("Original GIS service metadata unavailable")
    listing=service.get("layers")
    fields=layer.get("fields")
    if (service.get("error") or layer.get("error") or
        not isinstance(listing,list) or not isinstance(fields,list)
        or not 1<=len(fields)<=140 or
        layer.get("name")!=candidate["layer_name"] or
        not LAYER_NAME.fullmatch(layer["name"]) or
        layer.get("type")!="Feature Layer" or
        layer.get("geometryType")!="esriGeometryPoint"
        or not any(x.get("id")==int(p.path.rsplit("/",1)[1])
                   and x.get("name")==layer["name"] for x in listing if isinstance(x,dict))
        or not any(f.get("name")=="OBJECTID" and f.get("type")=="esriFieldTypeOID"
                   for f in fields if isinstance(f,dict))):
        raise ValueError("Official map server does not authenticate exact Flock point layer")
    names={f.get("name") for f in fields if isinstance(f,dict)}
    id_field=next((f for f in FIELDS if f in names),None)
    if not id_field:
        raise ValueError("Exact layer has no individual camera identifier")
    # Fetch all authoritative ArcGIS ObjectIDs twice. A response with
    # resultRecordCount alone can be silently truncated by maxRecordCount.
    def inventory_ids():
        data=get_official_json(url+"/query?"+urllib.parse.urlencode({
            "where":"1=1","returnIdsOnly":"true","f":"json"}))
        if not isinstance(data,dict) or data.get("error"):
            raise ValueError("Government camera ID inventory unavailable")
        if data.get("objectIdFieldName") not in (None,"OBJECTID"):
            raise ValueError("Government camera ID field changed")
        ids=data.get("objectIds")
        if (not isinstance(ids,list) or not 1<=len(ids)<=MAX_INVENTORY
            or any(type(i) is not int or i<=0 for i in ids)
            or len(set(ids))!=len(ids)):
            raise ValueError("Government camera ID inventory incomplete or duplicated")
        return sorted(ids)

    full_ids=inventory_ids()
    features=[]
    for start in range(0,len(full_ids),50):
        block=full_ids[start:start+50]
        query=urllib.parse.urlencode({
            "objectIds":",".join(map(str,block)),
            "outFields":"OBJECTID,"+id_field,
            "returnGeometry":"true","outSR":"4326","f":"json"})
        data=get_official_json(url+"/query?"+query)
        batch=data.get("features") if isinstance(data,dict) else None
        if (not isinstance(batch,list) or data.get("error")
            or data.get("exceededTransferLimit") or len(batch)!=len(block)):
            raise ValueError("Government camera ID batch was truncated")
        received=[item.get("attributes",{}).get("OBJECTID")
                  for item in batch if isinstance(item,dict)
                  and isinstance(item.get("attributes"),dict)]
        if (len(received)!=len(block) or set(received)!=set(block)
            or len(set(received))!=len(received)):
            raise ValueError("Government camera ID batch identities mismatch")
        features.extend(batch)
    if full_ids!=inventory_ids():
        raise ValueError("Government camera IDs changed while checking geometry")
    features.sort(key=lambda row:row["attributes"]["OBJECTID"])
    locations=[];seen=set()
    for item in features:
        att=item.get("attributes") if isinstance(item,dict) else None
        geom=item.get("geometry") if isinstance(item,dict) else None
        if not isinstance(att,dict) or not isinstance(geom,dict):
            raise ValueError("Camera feature lacks original GIS point")
        oid=att.get("OBJECTID")
        label=att.get(id_field)
        x,y=geom.get("x"),geom.get("y")
        if (type(oid) is not int or oid<=0 or oid in seen or
            not isinstance(label,str) or not 1<=len(label.strip())<=100 or
            type(x) not in (float,int) or type(y) not in (float,int) or
            not parent["bounds_west"]<=x<=parent["bounds_east"] or
            not parent["bounds_south"]<=y<=parent["bounds_north"]):
            raise ValueError("Camera identity/geometry ambiguous: withhold whole source")
        seen.add(oid)
        locations.append({"id":oid,"lat":round(y,7),"lon":round(x,7)})
    digest=hashlib.sha256(json.dumps({
        "url":url,"name":layer["name"],"fields":sorted(names),"locations":locations
    },sort_keys=True,separators=(",",":")).encode()).hexdigest()
    key=("gis_"+re.sub(r"[^a-z0-9_]","_",parent["source_key"])+"_"+
         hashlib.sha256(url.encode()).hexdigest()[:12])[:50]
    if len(key)<12:
        raise ValueError("Invalid derived evidence identity")
    return {
      "p_parent_source_key":parent["source_key"],
      "p_source_key":key,
      "p_layer_url":url,
      "p_layer_name":layer["name"],
      "p_camera_id_field":id_field,
      "p_layer_sha256":digest,
      "p_locations":locations,
    }


def run(dry_run=False,publish=False):
    result=Counter()
    checked=set()
    for parent,root,candidate in discovery_inputs():
        url=candidate["gis_layer_url"]
        if url in checked: continue
        checked.add(url)
        try:
            payload=verify_layer(parent,root,candidate)
            result["eligible_live_layers"]+=1
            print("Verified original government host / Flock point layer:",
                  parent["source_key"],url,"points",len(payload["p_locations"]))
            if not dry_run:
                value=api_request("rpc/register_derived_government_flock_gis",
                    method="POST",payload=payload)
                if value is not True:
                    raise ValueError("Database independently refused source registration")
                result["registered"]+=1
        except HTTPError as exc:
            # Surface the actual database reason. A duplicate is a deliberate
            # evidence hold; an unknown HTTP 400, permission failure, or
            # registration bug must not count as a successful verification.
            body=exc.read(1600).decode("utf8","replace")
            if ("Possible already published government camera" in body
                or "Not a distinct approved-host layer" in body):
                result["duplicate_or_existing_held"]+=1
            else:
                result["errors"]+=1
            result["held"]+=1
            print("Government layer NOT registered:",url,
                  "HTTP",exc.code,"database reason",body[:500])
        except ValueError as exc:
            result["held"]+=1
            print("Government source evidence held:",url,str(exc)[:220])
        except Exception as exc:
            result["held"]+=1
            result["errors"]+=1
            print("Government source registration failed:",url,
                  type(exc).__name__,str(exc)[:220])
    if publish and not dry_run and result["registered"]:
        verified=refresh_verified()
        result["new_public_pins"]=verified["published"]
        if verified["errors"]:
            raise RuntimeError("Verified source camera refresh failed after new approval")
    for key in ("eligible_live_layers","registered","held",
                "duplicate_or_existing_held","errors","new_public_pins"):
        print("Derived government GIS",key+":",result[key])
    print("ArcGIS-only unverified third-party publishers approved: 0")
    return result


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    a.add_argument("--publish",action="store_true")
    o=a.parse_args()
    result=run(o.dry_run,o.publish)
    if result["errors"]:
        raise SystemExit("A government GIS registration failed unexpectedly; check error logs")
