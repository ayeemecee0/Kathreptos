"""Reusable source-profile Flock government GIS verification.

Only owner-approved sources/profiles; community map labels cannot authorize
publication. No city-specific Python branch is required for future verified
sources. A failed or incomplete GIS response never revokes published data.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.parse
from collections import Counter

from auto_verify_flock_agenda import api_request
from auto_verify_camera_gis import (
    get_official_json, classify_camera_type, write_verified,
    mark_rechecked, fetch_existing, revoke_stale
)

LIMIT=1000
FIELD=re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,50}$")
FLOCK_LAYER=re.compile(r"^flock[_ ]cameras(?: - [A-Za-z][A-Za-z ]{0,60})?$",re.I)


def approved_sources():
    src=api_request("trusted_flock_gis_sources?select=source_key,gis_layer_url,"
        "government_evidence_url,jurisdiction_label,expected_id_field,"
        "bounds_south,bounds_west,bounds_north,bounds_east,source_status"
        "&source_status=eq.verified&limit=100")
    policies=api_request("gis_verification_profiles?select=source_key,"
        "expected_layer_name,identity_mode,vendor_field,camera_id_field,"
        "service_evidence_mode,profile_status&profile_status=eq.verified&limit=100")
    roots=api_request("gis_government_host_authorities?select=authority_key,"
        "government_gis_host,official_government_page,allowed_layer_path,"
        "jurisdiction_label,verification_status&verification_status=eq.verified&limit=100")
    if not all(isinstance(x,list) and len(x)<100 for x in (src,policies,roots)):
        raise ValueError("Untrusted or truncated GIS authority registry")
    ps={x["source_key"]:x for x in policies}
    rs={x["authority_key"]:x for x in roots}
    checked=[]
    for s in src:
        p=ps.get(s["source_key"])
        if not p:
            raise ValueError("Verified government source has no owner-approved GIS policy")
        authorize(s,p,rs.get(s["source_key"]))
        checked.append((s,p))
    return checked


def authorize(s,p,r):
    if (s.get("source_status")!="verified" or p.get("profile_status")!="verified"
        or p.get("source_key")!=s.get("source_key") or s.get("expected_id_field")!="OBJECTID"):
        raise ValueError("GIS authority not independently verified")
    a=urllib.parse.urlsplit(s.get("gis_layer_url") or "")
    b=urllib.parse.urlsplit(s.get("government_evidence_url") or "")
    if (a.scheme!="https" or b.scheme!="https" or a.username or a.password or
        b.username or b.password or a.port not in (None,443) or
        b.port not in (None,443) or a.query or a.fragment or
        not re.fullmatch(r"/.+/(MapServer|FeatureServer)/\d+",a.path)):
        raise ValueError("Unverified government GIS URL")
    if r:
        if (r.get("verification_status")!="verified" or
            s["gis_layer_url"]!="https://"+r["government_gis_host"]+r["allowed_layer_path"] or
            s["government_evidence_url"]!=r["official_government_page"] or
            s["jurisdiction_label"]!=r["jurisdiction_label"]):
            raise ValueError("GIS URL/authority differs from owner-reviewed government root")
    else:
        # Legacy vendor-specific original-government GIS records are valid,
        # but not untrusted layer-name inference without a reviewed host root.
        if (p.get("identity_mode")!="per_feature_vendor" or
            not a.hostname.endswith("."+b.hostname)):
            raise ValueError("No reviewed government root for a Flock-only layer")
    bounds=[s.get(k) for k in ("bounds_south","bounds_west","bounds_north","bounds_east")]
    if (any(type(x) not in (int,float) for x in bounds) or
        not (17<=bounds[0]<bounds[2]<=72 and -180<=bounds[1]<bounds[3]<=-64)):
        raise ValueError("Invalid official GIS jurisdiction bounds")
    if p.get("identity_mode")=="per_feature_vendor":
        if (not FIELD.fullmatch(p.get("vendor_field") or "") or
            p.get("service_evidence_mode")!="official_program_plus_vendor"):
            raise ValueError("Missing individual Flock vendor evidence policy")
    elif p.get("identity_mode")=="official_flock_layer":
        if (not r or not FLOCK_LAYER.fullmatch(p.get("expected_layer_name") or "") or
            not FIELD.fullmatch(p.get("camera_id_field") or "") or
            (p.get("vendor_field") is not None and not FIELD.fullmatch(p["vendor_field"])) or
            p.get("service_evidence_mode") not in
              ("listed_flock_layer","explicit_flock_service_text")):
            raise ValueError("Unapproved government layer-name Flock attribution")
    else:
        raise ValueError("Unsupported GIS identity policy")
    return True


def check_metadata(s,p,service,layer):
    if (not isinstance(service,dict) or not isinstance(layer,dict) or
        service.get("error") or layer.get("error") or
        layer.get("type")!="Feature Layer" or layer.get("geometryType")!="esriGeometryPoint"):
        raise ValueError("Original government GIS point metadata missing")
    fields=layer.get("fields")
    if not isinstance(fields,list) or not 1<=len(fields)<=140:
        raise ValueError("Malformed government GIS fields")
    names={f.get("name") for f in fields if isinstance(f,dict)}
    if (s["expected_id_field"] not in names or
        not any(f.get("name")=="OBJECTID" and f.get("type")=="esriFieldTypeOID"
        for f in fields if isinstance(f,dict))):
        raise ValueError("Government object ID schema is unsupported")
    if p["identity_mode"]=="per_feature_vendor":
        if p["vendor_field"] not in names:
            raise ValueError("Government per-feature vendor field absent")
    else:
        expected=p["expected_layer_name"]
        if (layer.get("name")!=expected or p["camera_id_field"] not in names or
            (p.get("vendor_field") is not None and p["vendor_field"] not in names)):
            raise ValueError("Flock-only source layer name or identifier changed")
        if p["service_evidence_mode"]=="listed_flock_layer":
            layer_id=int(s["gis_layer_url"].rsplit("/",1)[1])
            listing=service.get("layers")
            if not isinstance(listing,list) or not any(
                f.get("id")==layer_id and f.get("name")==expected
                for f in listing if isinstance(f,dict)):
                raise ValueError("Government GIS service does not list reviewed Flock point layer")
        else:
            info=service.get("documentInfo") or {}
            descriptor=" ".join(str(x or "") for x in
                (service.get("mapName"),service.get("serviceDescription"),
                 service.get("description"),info.get("Keywords"),info.get("Title"))).lower()
            if "flock" not in descriptor or not ("camera" in descriptor or "cctv" in descriptor):
                raise ValueError("Government GIS service vendor description changed")


def query_gis(s,p):
    parent=s["gis_layer_url"].rsplit("/",1)[0]
    check_metadata(s,p,get_official_json(parent+"?f=json"),
                   get_official_json(s["gis_layer_url"]+"?f=json"))
    fields=["OBJECTID"]
    if p["identity_mode"]=="per_feature_vendor":
        fields.append(p["vendor_field"])
    else:
        fields.append(p["camera_id_field"])
        if p.get("vendor_field"):fields.append(p["vendor_field"])
    qs=urllib.parse.urlencode({"where":"1=1","outFields":",".join(sorted(set(fields))),
         "returnGeometry":"true","outSR":"4326","orderByFields":"OBJECTID ASC",
         "resultRecordCount":str(LIMIT),"f":"json"})
    return get_official_json(s["gis_layer_url"]+"/query?"+qs)


def verify_points(s,p,data):
    if (not isinstance(data,dict) or data.get("error") or
        not isinstance(data.get("features"),list) or
        not 1<=len(data["features"])<LIMIT or data.get("exceededTransferLimit")):
        raise ValueError("Official GIS data empty, malformed or truncated")
    records=[];holds=Counter();ids=set()
    south,west,north,east=[s[k] for k in ("bounds_south","bounds_west","bounds_north","bounds_east")]
    for f in data["features"]:
        a=f.get("attributes") if isinstance(f,dict) else None
        g=f.get("geometry") if isinstance(f,dict) else None
        if not isinstance(a,dict) or not isinstance(g,dict):
            holds["missing GIS fields or geometry"]+=1;continue
        oid=a.get("OBJECTID")
        if type(oid) is not int or oid<=0 or oid in ids:
            raise ValueError("Government GIS has malformed or duplicate object identifier")
        ids.add(oid)
        if p["identity_mode"]=="per_feature_vendor":
            vendor=a.get(p["vendor_field"])
            if not classify_camera_type(vendor):
                holds["not identified as Flock camera"]+=1;continue
            camera_type=" ".join(vendor.split())
        else:
            identifier=a.get(p["camera_id_field"])
            if not isinstance(identifier,str) or not 1<=len(identifier.strip())<=100:
                holds["no individual camera identifier"]+=1;continue
            # A mixed government point layer may include school/traffic
            # equipment. Filter each feature if an additional reviewed
            # per-camera manufacturer/type field is defined.
            if p.get("vendor_field") and not classify_camera_type(a.get(p["vendor_field"])):
                holds["not a Flock camera per original GIS field"]+=1;continue
            # Preserve earlier evidence fingerprints for unchanged published
            # sources, avoiding fictitious withdrawal/republication history.
            camera_type=("Flock (county Sheriff GIS layer)" if
                p["service_evidence_mode"]=="explicit_flock_service_text" else
                "Flock (city Public Works GIS layer)")
        lat,lon=g.get("y"),g.get("x")
        if (type(lat) not in (int,float) or type(lon) not in (int,float) or
            not south<=lat<=north or not west<=lon<=east):
            holds["invalid verified-location coordinates"]+=1;continue
        lat,lon=round(lat,7),round(lon,7)
        digest=hashlib.sha256(json.dumps({
          "layer":s["gis_layer_url"],"object_id":oid,
          "camera_type":camera_type,"latitude":lat,"longitude":lon
        },sort_keys=True,separators=(",",":")).encode()).hexdigest()
        records.append({
          "record_key":f"gis-{s['source_key']}-{oid}-{digest[:12]}",
          "label":f"Flock ALPR · {s['jurisdiction_label']} GIS #{oid}",
          "jurisdiction_label":s["jurisdiction_label"],
          "latitude":lat,"longitude":lon,"location_accuracy":"exact",
          "uncertainty_radius_m":0,"source_type":"official_government",
          "source_url":s["gis_layer_url"],
          "evidence_summary":("Official government point camera source: "+
             camera_type+". The exact GIS location and Flock identification "
             "are source-backed; no device uptime or license plate read is established."),
          "evidence_sha256":digest,
          "verification_method":"official_georeferenced_camera_record_v1",
          "last_confirmed_on":dt.date.today().isoformat()
        })
    return records,holds,len(data["features"])


def sync(dry_run=False):
    total=Counter()
    for s,p in approved_sources():
        try:
            rows,held,n=verify_points(s,p,query_gis(s,p))
            total["sources_checked"]+=1;total["features_checked"]+=n
            total["eligible"]+=len(rows)
            print("PROFILE GIS SOURCE:",s["source_key"],"features",n,
                  "verified",len(rows),"held",dict(held))
            if dry_run:continue
            if not rows:raise ValueError("Zero independently qualifying camera records; withholding reconciliation")
            old=fetch_existing("gis-"+s["source_key"]+"-")
            keys={r["record_key"] for r in rows}
            for item in rows:
                if write_verified(item):total["published"]+=1
                else:
                    mark_rechecked(item["record_key"]);total["rechecked"]+=1
            for record in old:
                if record["record_key"] not in keys and revoke_stale(record["record_key"]):
                    total["withdrawn"]+=1
        except Exception as exc:
            total["errors"]+=1
            print("PROFILE GIS HELD:",s["source_key"],type(exc).__name__,str(exc)[:180])
    for k in ("sources_checked","features_checked","eligible","published",
              "rechecked","withdrawn","errors"):
        print("PROFILE GIS",k+":",total[k])
    return total


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    result=sync(a.parse_args().dry_run)
    if result["errors"]:raise SystemExit("Source-profile GIS verification failed")
