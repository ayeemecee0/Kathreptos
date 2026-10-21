"""Automatically publish ONLY Flock cameras explicitly identified in trusted official GIS.

No geocoding from street names, no invented points, no OSM/community auto-publish.
The source authority is independently pinned by database-owner-reviewed migration
019. Missing, unclassified, displaced, or changed GIS records are held privately.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.parse
import urllib.request
from collections import Counter

from auto_verify_flock_agenda import api_request
from discover_government_records import USER_AGENT

MAX_GIS_FEATURES = 1000
MAX_GIS_BYTES = 2_000_000
# Explicit city government GIS host has been individually checked against
# municipality's public Flock program. New sources require code review AND
# database-owner approval, not automatically discovered authority.
SOURCE_HOST_BINDINGS = {
    "monroe_wa": ("gis.monroewa.gov", "monroewa.gov", "Monroe, WA"),
}
EXACT_FLOCK = re.compile(r"(?:^|\b)flock(?:\s+safety|\s+falcon)?(?:\b|$)", re.I)
NON_ALPR = re.compile(r"\b(?:raven|gunshot|audio|condor|ptz|cctv|traffic\s+signal)\b", re.I)


def get_official_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=24) as response:
        data = response.read(MAX_GIS_BYTES + 1)
        if response.geturl() != url:
            raise ValueError("Government GIS URL was redirected")
    if len(data) > MAX_GIS_BYTES or not data:
        raise ValueError("Government GIS JSON missing or over size limit")
    return json.loads(data)


def trusted_source(row):
    if not isinstance(row, dict) or row.get("source_status") != "verified":
        return None
    key = row.get("source_key")
    bind = SOURCE_HOST_BINDINGS.get(key)
    if not bind:
        return None
    layer = row.get("gis_layer_url")
    evidence = row.get("government_evidence_url")
    if not isinstance(layer, str) or not isinstance(evidence, str):
        return None
    expected_host, government_host, jurisdiction = bind
    parsed = urllib.parse.urlsplit(layer)
    proof = urllib.parse.urlsplit(evidence)
    if (parsed.scheme != "https" or parsed.netloc != expected_host or parsed.query or parsed.fragment
        or proof.scheme != "https" or proof.hostname not in (government_host, "www."+government_host)
        or proof.username or proof.password or proof.port not in (None,443)
        or row.get("jurisdiction_label") != jurisdiction
        or not re.fullmatch(r"/citygis/rest/services/UtilityData/Street_Layers/MapServer/22",parsed.path)
        or row.get("expected_camera_type_field") != "CameraType"
        or row.get("expected_id_field") != "OBJECTID"):
        return None
    bounds = [row.get(p) for p in (
        "bounds_south", "bounds_west", "bounds_north", "bounds_east")]
    if any(type(v) not in (int,float) for v in bounds):
        return None
    if not (47.8 <= bounds[0] < bounds[2] <= 48.0 and
            -122.12 <= bounds[1] < bounds[3] <= -121.80):
        return None
    return row


def fetch_verified_sources():
    rows = api_request(
        "trusted_flock_gis_sources?select=source_key,gis_layer_url,government_evidence_url,"
        "jurisdiction_label,expected_camera_type_field,expected_id_field,bounds_south,"
        "bounds_west,bounds_north,bounds_east,source_status"
        "&source_status=eq.verified&limit=100")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise ValueError("Trusted GIS registry truncated or malformed")
    return [source for row in rows if (source := trusted_source(row))]


def classify_camera_type(value):
    """Require GIS record itself to explicitly name Flock ALPR vendor."""
    if not isinstance(value, str):
        return False
    value = " ".join(value.split())
    return bool(len(value) <= 50 and EXACT_FLOCK.search(value) and not NON_ALPR.search(value))


def decode_features(source, payload):
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("Government GIS query did not return a clean response")
    features = payload.get("features")
    if (not isinstance(features,list) or len(features)>MAX_GIS_FEATURES
        or payload.get("exceededTransferLimit") is True):
        raise ValueError("Government GIS results missing/truncated/oversized")
    if not features:
        raise ValueError("Government GIS returned zero features: cannot corroborate inventory")
    eligible = []
    held = Counter()
    all_ids=set()
    for feature in features:
        if not isinstance(feature,dict):
            held["malformed feature"]+=1;continue
        attrs=feature.get("attributes")
        geom=feature.get("geometry")
        if not isinstance(attrs,dict) or not isinstance(geom,dict):
            held["missing feature attributes or point geometry"]+=1;continue
        identity=attrs.get("OBJECTID")
        if type(identity) is not int or identity <=0 or identity in all_ids:
            held["missing or conflicting government GIS ID"]+=1;continue
        all_ids.add(identity)
        if not classify_camera_type(attrs.get("CameraType")):
            held["vendor/model not explicitly Flock ALPR"]+=1;continue
        longitude,latitude=geom.get("x"),geom.get("y")
        if type(longitude) not in (int,float) or type(latitude) not in (int,float):
            held["government GIS coordinates malformed"]+=1;continue
        s,w,n,e=[source[k] for k in (
            "bounds_south","bounds_west","bounds_north","bounds_east")]
        if not s<=latitude<=n or not w<=longitude<=e:
            held["government GIS coordinate outside source jurisdiction"]+=1;continue
        latitude,longitude=round(latitude,7),round(longitude,7)
        camera_type=" ".join(attrs["CameraType"].split())
        proof = json.dumps({
            "layer":source["gis_layer_url"],"object_id":identity,
            "camera_type":camera_type,"latitude":latitude,"longitude":longitude,
        },sort_keys=True,separators=(',',':'))
        sha=hashlib.sha256(proof.encode()).hexdigest()
        record_key=f"gis-{source['source_key']}-{identity}-{sha[:12]}"
        eligible.append({
            "record_key":record_key,
            "label":f"Flock ALPR · {source['jurisdiction_label']} GIS #{identity}",
            "jurisdiction_label":source["jurisdiction_label"],
            "latitude":latitude,"longitude":longitude,
            "location_accuracy":"exact","uncertainty_radius_m":0,
            "source_type":"official_government",
            "source_url":source["gis_layer_url"],
            "evidence_summary":(
                f"Municipal public GIS camera layer. Exact OBJECTID {identity}; "
                f"government CameraType field says '{camera_type}'. "
                "The city separately identifies its camera program as Flock Safety; "
                "this is published equipment location, not evidence of operation or plate reads."),
            "evidence_sha256":sha,
            "verification_method":"official_georeferenced_camera_record_v1",
            "last_confirmed_on":dt.date.today().isoformat(),
        })
    return eligible,held,len(features)


def gis_query(source):
    args=urllib.parse.urlencode({
        "where":"1=1",
        "outFields":"OBJECTID,MRID,CameraType,Facing",
        "returnGeometry":"true",
        "outSR":"4326",
        "orderByFields":"OBJECTID ASC",
        "resultRecordCount":str(MAX_GIS_FEATURES),
        "f":"json",
    })
    return get_official_json(source["gis_layer_url"]+"/query?"+args)


def write_verified(item):
    rows=api_request(
        "flock_camera_locations?on_conflict=record_key",
        method="POST",payload=[item],
        prefer="resolution=ignore-duplicates,return=representation")
    if not isinstance(rows,list) or len(rows)>1:
        raise ValueError("Unexpected published government GIS receipt")
    return bool(rows)


def fetch_existing(prefix):
    query=urllib.parse.urlencode({
        "select":"record_key,verification_status",
        "record_key":"like."+prefix+"*",
        "verification_status":"eq.verified",
        "limit":"1000",
    })
    rows=api_request("flock_camera_locations?"+query)
    if not isinstance(rows,list) or len(rows)>=1000:
        raise ValueError("Existing official camera inventory too large to reconcile")
    return rows


def revoke_stale(key):
    qs=urllib.parse.urlencode({
        "record_key":"eq."+key,
        "verification_status":"eq.verified"
    })
    rows=api_request("flock_camera_locations?"+qs,
        method="PATCH",payload={"verification_status":"revoked"},
        prefer="return=representation")
    if not isinstance(rows,list) or len(rows)>1:
        raise ValueError("Invalid stale camera withdrawal receipt")
    return bool(rows)


def sync(dry_run=False):
    sources=fetch_verified_sources()
    counts=Counter()
    for source in sources:
        name=source["source_key"]
        try:
            payload=gis_query(source)
            qualified,reasons,total=decode_features(source,payload)
            counts["features_checked"]+=total
            counts["eligible"]+=len(qualified)
            print("Verified GIS inventory:",name,"total",total,"explicit Flock cameras",len(qualified))
            for reason,n in reasons.items():
                print("GIS feature held:",name,reason,n)
            keys={x["record_key"] for x in qualified}
            if dry_run:
                print("DRY-RUN government GIS locations:",name,len(keys))
                continue
            # Never infer current operation, never auto-verify manufacturer based
            # solely on municipality label or unqualified CameraType.
            for item in qualified:
                if write_verified(item):
                    counts["published"]+=1
                else:
                    counts["existing"]+=1
            # Recheck: when the official, complete inventory changes,
            # withdraw locations whose exact record+coordinate fingerprint
            # is no longer present. An empty/malformed inventory cannot revoke.
            existing=fetch_existing("gis-"+name+"-")
            for old in existing:
                if old["record_key"] not in keys and revoke_stale(old["record_key"]):
                    counts["revoked"]+=1
        except Exception as exc:
            counts["errors"]+=1
            print("Official GIS source held:",name,type(exc).__name__,str(exc)[:200])
    for k in ("features_checked","eligible","published","existing","revoked","errors"):
        print("Camera GIS",k+":",counts[k])
    return counts


if __name__=="__main__":
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--dry-run",action="store_true")
    sync(dry_run=arg.parse_args().dry_run)
