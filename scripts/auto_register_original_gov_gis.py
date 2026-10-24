"""Find NEW independently verifiable US .gov-owned Flock camera GIS sources.

Unlike prior pipelines restricted to five already approved municipalities, this
worker can seed a new exact source authority without writing city-specific
code, but ONLY when the original government .gov Flock disclosure directly
links an ArcGIS camera point layer hosted on the SAME .gov apex. The worker
re-reads the exact original HTML, GIS layer schema, entire bounded point
inventory and stable camera IDs before invoking a restrictive database RPC.
Uncertain records remain private; jurisdiction is labeled by verifiable .gov
hostname rather than an inferred city name.
"""
import argparse
import hashlib
import json
import re
import urllib.parse
from collections import Counter
from urllib.error import HTTPError

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from auto_verify_camera_gis import get_official_json
from auto_verify_camera_profiles import check_metadata, verify_points, sync
from corroborate_candidate_government_links import direct_candidate_links
from discover_government_gis_links import fetch_government_page
from discover_camera_gis_sources import stage_candidate
from government_domain_registry import public_dns

LAYER=re.compile(
    r"^https://(?:[a-z0-9-]+\.)+gov/[A-Za-z0-9_/-]+/"
    r"(?:MapServer|FeatureServer)/[0-9]+$")
FLOCK=re.compile(r"^flock[_ ]cameras(?: - [A-Za-z][A-Za-z ]{0,60})?$",re.I)
IDENTIFIERS=("CameraID","NAME","ID","Camera_ID")
TYPES=("CameraType","Type","Manufacturer")
MAX_FEATURES=250


def same_gov_apex(page,layer):
    p,l=urllib.parse.urlsplit(page),urllib.parse.urlsplit(layer)
    if (not LAYER.fullmatch(layer) or
        p.scheme!="https" or p.username or p.password or p.port is not None or
        not p.hostname or not p.hostname.endswith(".gov") or
        l.port is not None or l.username or l.password or l.query or l.fragment):
        return False
    x=p.hostname.split(".")
    y=l.hostname.split(".")
    return len(x)>=2 and len(y)>=2 and x[-2:]==y[-2:] and x[-2]!="gov"


SERVICE_ROOT=re.compile(
  r"^https://(?:[a-z0-9-]+\.)+gov/[A-Za-z0-9_/-]+/(?:MapServer|FeatureServer)/?$",
  re.I)


def resolve_exact_original_camera_layer(page,link):
    """Qualify one government-linked GIS service only if it has one Flock layer."""
    if same_gov_apex(page,link):
        return link,link,None
    if not isinstance(link,str) or not SERVICE_ROOT.fullmatch(link):
        raise ValueError("Not an original government GIS camera layer or service root")
    p=urllib.parse.urlsplit(page)
    l=urllib.parse.urlsplit(link)
    if (p.scheme!="https" or l.scheme!="https" or p.username or p.password
        or l.username or l.password or p.port is not None or l.port is not None
        or l.query or l.fragment
        or p.hostname.split(".")[-2:]!=l.hostname.split(".")[-2:]):
        raise ValueError("ArcGIS service not tied to original government authority")
    clean=link.rstrip("/")
    service=get_official_json(clean+"?f=json")
    items=service.get("layers") if isinstance(service,dict) else None
    if not isinstance(items,list) or len(items)>300:
        raise ValueError("Original government GIS service listing missing")
    matches=[(x["id"],x["name"]) for x in items if isinstance(x,dict)
        and type(x.get("id")) is int and 0<=x["id"]<1000
        and isinstance(x.get("name"),str) and FLOCK.fullmatch(x["name"])]
    if len(matches)!=1:
        raise ValueError("Government service contains zero or multiple Flock camera layers")
    identity,name=matches[0]
    return clean+"/"+str(identity),clean,name


def private_government_pages():
    pages=fetch_all(api_request,"government_gis_search_queue?select=page_url,page_sha256,"
       "gis_links,candidate_status&candidate_status=eq.unverified"
       "&limit=100","page_url")
    return [p for p in pages if isinstance(p.get("gis_links"),list)
            and p["gis_links"]]


def qualified_original_layer(page,url):
    service_url=url.rsplit("/",1)[0]
    service=get_official_json(service_url+"?f=json")
    layer=get_official_json(url+"?f=json")
    name=layer.get("name") if isinstance(layer,dict) else None
    if not isinstance(name,str) or not FLOCK.fullmatch(name):
        raise ValueError("Original .gov GIS metadata does not identify Flock cameras")
    fields=layer.get("fields",[])
    names={x.get("name") for x in fields if isinstance(x,dict)}
    identifier=next((f for f in IDENTIFIERS if f in names),None)
    vendor=next((f for f in TYPES if f in names),None)
    if not identifier:
        raise ValueError("Government Flock point layer has no individual camera identifier")
    host=urllib.parse.urlsplit(page).hostname
    temp={
      "source_key":"autogov_probe","gis_layer_url":url,
      "expected_id_field":"OBJECTID",
      "jurisdiction_label":"Government GIS: "+host,
    }
    policy={"identity_mode":"official_flock_layer",
            "camera_id_field":identifier,"vendor_field":vendor,
            "expected_layer_name":name,"service_evidence_mode":"listed_flock_layer"}
    check_metadata(temp,policy,service,layer)
    fields_out={identifier,"OBJECTID"}|({vendor} if vendor else set())
    # A single resultRecordCount request is NOT a complete-inventory proof:
    # ArcGIS services may silently apply maxRecordCount even when they omit
    # exceededTransferLimit. Compare original returnIdsOnly inventories before
    # and after fetching every exact feature by ID in bounded chunks.
    def original_ids():
        snapshot=get_official_json(url+"/query?"+urllib.parse.urlencode({
            "where":"1=1","returnIdsOnly":"true","f":"json"}))
        if not isinstance(snapshot,dict) or snapshot.get("error"):
            raise ValueError("Government original GIS ObjectID inventory unavailable")
        if snapshot.get("objectIdFieldName") not in (None,"OBJECTID"):
            raise ValueError("Government original GIS ObjectID field changed")
        ids=snapshot.get("objectIds")
        if (not isinstance(ids,list) or not 1<=len(ids)<=MAX_FEATURES or
            any(type(oid) is not int or oid<=0 for oid in ids) or
            len(set(ids))!=len(ids)):
            raise ValueError("Government original GIS ObjectID inventory invalid or oversized")
        return sorted(ids)

    original_inventory=original_ids()
    original_set=set(original_inventory)
    fields_out={identifier,"OBJECTID"}|({vendor} if vendor else set())
    features=[]
    for start in range(0,len(original_inventory),50):
        block=original_inventory[start:start+50]
        q=urllib.parse.urlencode({
            "objectIds":",".join(map(str,block)),
            "outFields":",".join(sorted(fields_out)),
            "returnGeometry":"true","outSR":"4326","f":"json"})
        result=get_official_json(url+"/query?"+q)
        batch=result.get("features") if isinstance(result,dict) else None
        if (not isinstance(batch,list) or len(batch)!=len(block) or
            result.get("error") or result.get("exceededTransferLimit")):
            raise ValueError("Government original GIS feature batch incomplete")
        expected=set(block)
        actual=[item.get("attributes",{}).get("OBJECTID")
                for item in batch if isinstance(item,dict)
                and isinstance(item.get("attributes"),dict)]
        if (len(actual)!=len(block) or set(actual)!=expected or
            len(set(actual))!=len(actual)):
            raise ValueError("Government original GIS feature identity mismatch")
        features.extend(batch)
    if original_inventory!=original_ids():
        raise ValueError("Government original GIS inventory changed during verification")
    features.sort(key=lambda item:item["attributes"]["OBJECTID"])
    data={"features":features}
    if len(features)!=len(original_set):
        raise ValueError("Government original GIS feature inventory incomplete")
    locations=[]
    for f in features:
        attrs=f.get("attributes") if isinstance(f,dict) else None
        geometry=f.get("geometry") if isinstance(f,dict) else None
        if not isinstance(attrs,dict) or not isinstance(geometry,dict):
            raise ValueError("Original camera feature lacks georeferencing")
        oid=attrs.get("OBJECTID")
        lat,lon=geometry.get("y"),geometry.get("x")
        if type(oid) is not int or type(lat) not in (int,float) or type(lon) not in (int,float):
            raise ValueError("Government point geometry/identity malformed")
        locations.append({"id":oid,"lat":round(lat,7),"lon":round(lon,7)})
    south=min(x["lat"] for x in locations)-.05
    north=max(x["lat"] for x in locations)+.05
    west=min(x["lon"] for x in locations)-.05
    east=max(x["lon"] for x in locations)+.05
    temp.update(bounds_south=south,bounds_north=north,
                bounds_west=west,bounds_east=east)
    records,held,total=verify_points(temp,policy,data)
    if held or len(records)!=total or len({loc["id"] for loc in locations})!=total:
        raise ValueError("Government source camera points partially ambiguous/non-Flock; withhold entire layer")
    sha=hashlib.sha256(json.dumps(
        {"url":url,"layer":name,"locations":locations},sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    candidate={
      "gis_layer_url":url,"layer_name":name,
      "geometry_type":"esriGeometryPoint",
      "object_id_field":"OBJECTID",
      "layer_purpose":"Unverified until original .gov Flock disclosure link, exact same government-domain GIS metadata, individual camera IDs and nonduplicated point geometry are independently checked. This research record is not a public camera inventory.",
      "public_gov_context_url":page,"trust_status":"unverified",
    }
    return identifier,vendor,locations,sha,candidate


def run(dry_run=False):
    stats=Counter()
    seen=set()
    for source in private_government_pages():
        page=source["page_url"]
        for original_link in source["gis_links"][:25]:
            if not isinstance(original_link,str) or original_link in seen:
                continue
            seen.add(original_link)
            try:
                url,linked_url,layer_name=resolve_exact_original_camera_layer(
                    page,original_link)
                ph=urllib.parse.urlsplit(page).hostname
                lh=urllib.parse.urlsplit(url).hostname
                if not public_dns(ph) or not public_dns(lh):
                    raise ValueError("Original government host failed public DNS checks")
                doc,digest=fetch_government_page(page)
                confirmations=direct_candidate_links(doc,page,digest,
                    "Government GIS: "+ph,
                    {url:{"layer_name":layer_name or "Flock Cameras"}})
                if (len(confirmations)!=1 or confirmations[0]["gis_layer_url"]!=url
                    or confirmations[0]["discovery_method"]!=(
                        "government_page_direct_anchor_v1" if linked_url==url
                        else "government_page_direct_service_v1")):
                    raise ValueError("Original .gov Flock page no longer links exact camera layer or unambiguous service")
                field,vendor,points,layer_hash,candidate=qualified_original_layer(page,url)
                stats["qualified_live_layers"]+=1
                if dry_run:continue
                if digest!=source["page_sha256"]:
                    # The same exact original government Flock GIS link still
                    # exists, and current point metadata/geometry was verified.
                    # Preserve an append-only digest trail before advancing
                    # the private discovery page's fingerprint.
                    refreshed=api_request("rpc/refresh_unverified_gov_gis_page_digest",
                      method="POST",payload={
                         "p_page_url":page,
                         "p_expected_old_sha":source["page_sha256"],
                         "p_current_live_sha":digest,
                         "p_existing_layer_url":linked_url,
                      })
                    if refreshed is not True:
                        raise ValueError("Government source evidence refresh refused")
                    source["page_sha256"]=digest
                    stats["government_page_digest_refreshed"]+=1
                # Stage candidate privately before any request for government
                # source authority, never directly write public coordinates.
                stage_candidate(candidate)
                key="autogov_"+hashlib.sha256((page+url).encode()).hexdigest()[:20]
                payload={
                  "p_source_key":key,"p_page_url":page,"p_gis_layer_url":url,
                  "p_layer_name":candidate["layer_name"],
                  "p_camera_id_field":field,"p_vendor_field":vendor,
                  "p_page_sha256":digest,"p_layer_sha256":layer_hash,
                  "p_locations":points,
                }
                confirmed=api_request("rpc/register_original_gov_flock_source",
                   method="POST",payload=payload)
                if confirmed is not True:
                    raise ValueError("Owner-bound government source registration declined")
                stats["registered"]+=1
            except HTTPError as ex:
                # Publication conflicts are evidence holds; unexpected
                # database or authentication errors must fail CI visibly.
                response=ex.read(1200).decode("utf8","replace")
                stats["held"]+=1
                if not any(note in response for note in
                   ("possible existing published camera",
                    "No independently corroborated original .gov source",
                    "too broad to infer a safe local verification envelope")):
                    stats["errors"]+=1
                print("Government source registration refused:",url,
                      ex.code,response[:500])
            except ValueError as ex:
                stats["held"]+=1
                print("New original government source lacks sufficient evidence:",
                      url,str(ex)[:220])
            except Exception as ex:
                stats["held"]+=1
                stats["errors"]+=1
                print("Unexpected original government source verifier failure:",
                      url,type(ex).__name__,str(ex)[:220])
    if not dry_run and stats["registered"]:
        refreshed=sync()
        stats["new_verified_public_camera_pins"]=refreshed["published"]
        if refreshed["errors"]:
            stats["errors"]+=refreshed["errors"]
    for key in ("qualified_live_layers","registered","new_verified_public_camera_pins",
                "government_page_digest_refreshed","held","errors"):
        print("Auto-first-party government GIS",key+":",stats[key])
    print("Newly trusted ArcGIS Online private/community organizations: 0")
    return stats


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    out=run(a.parse_args().dry_run)
    if out["errors"]:raise SystemExit("Government Flock source verification incomplete")
