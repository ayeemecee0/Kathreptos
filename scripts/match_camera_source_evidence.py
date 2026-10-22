"""Attach independent OSM reports to ALREADY verified government GIS points.

No public camera insert/update; this job only creates private 30 m evidence
matches. It is not evidence of operation, and duplicate OSM/GIS representations
must never count as two cameras.
"""
import argparse
import math
import urllib.parse
from collections import Counter

from auto_verify_flock_agenda import api_request
from auto_verify_camera_gis import fetch_verified_sources

MAX_POINTS_PER_SOURCE=400
MAX_CANDIDATES_PER_SOURCE=450
MAX_DISTANCE_M=30.0
AMBIGUOUS_MARGIN_M=5.0


def bounded_query(table, fields, filters, cap):
    qs=urllib.parse.urlencode({"select":fields,**filters,"limit":str(cap)})
    rows=api_request(table+"?"+qs)
    if not isinstance(rows,list) or len(rows)>=cap:
        raise ValueError("Incomplete or invalid bounded camera evidence query")
    return rows


def official_points(source):
    rows=bounded_query(
       "flock_camera_locations",
       "record_key,latitude,longitude,source_url,verification_status,location_accuracy",
       {"verification_status":"eq.verified","source_url":"eq."+source["gis_layer_url"]},
       MAX_POINTS_PER_SOURCE)
    return [x for x in rows if x.get("location_accuracy")=="exact"
            and x.get("source_url")==source["gis_layer_url"]]


def candidate_points(points):
    if not points:
        return []
    lat=[float(x["latitude"]) for x in points]
    lon=[float(x["longitude"]) for x in points]
    margin=0.0007
    bounds={
       "latitude":"gte."+str(min(lat)-margin),
       "longitude":"gte."+str(min(lon)-margin),
       "source_kind":"eq.osm_public_dataset",
       "candidate_status":"eq.unverified",
    }
    # PostgREST supports ANDed repeated filters only when separately encoded.
    qs=urllib.parse.urlencode({
       "select":"candidate_key,latitude,longitude,source_kind",
       **bounds,
       "limit":str(MAX_CANDIDATES_PER_SOURCE),
    })
    qs+="&latitude="+urllib.parse.quote("lte."+str(max(lat)+margin))
    qs+="&longitude="+urllib.parse.quote("lte."+str(max(lon)+margin))
    result=api_request("flock_camera_discovery_candidates?"+qs)
    if not isinstance(result,list) or len(result)>=MAX_CANDIDATES_PER_SOURCE:
        raise ValueError("Unverified community report area is too crowded or truncated")
    return result


def meters(a,b):
    lat1,lon1=[float(x) for x in a]
    lat2,lon2=[float(x) for x in b]
    dlat=math.radians(lat2-lat1)
    dlon=math.radians(lon2-lon1)
    x=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(x)))


def choose_match(candidate,official):
    scores=[]
    loc=(candidate["latitude"],candidate["longitude"])
    for p in official:
        distance=meters(loc,(p["latitude"],p["longitude"]))
        if distance<=MAX_DISTANCE_M:
            scores.append((distance,p["record_key"]))
    scores.sort()
    if not scores:
        return None,"no close official match"
    if len(scores)>1 and scores[1][0]-scores[0][0]<AMBIGUOUS_MARGIN_M:
        return None,"ambiguous multiple government cameras"
    return {
       "candidate_key":candidate["candidate_key"],
       "verified_camera_key":scores[0][1],
       "matching_method":"trusted_gis_to_osm_30m_v1",
       # DB independently calculates and overwrites this value.
       "distance_m":round(scores[0][0],3),
    },None


def save_match(item):
    receipt=api_request(
       "flock_camera_source_matches?on_conflict=candidate_key,verified_camera_key",
       method="POST",payload=[item],
       prefer="resolution=ignore-duplicates,return=minimal")
    if receipt is not None:
        raise ValueError("Unexpected community corroboration staging receipt")


def run(dry_run=False):
    count=Counter()
    for source in fetch_verified_sources():
        try:
            approved=official_points(source)
            candidates=candidate_points(approved)
            count["official_points"]+=len(approved)
            count["candidate_points"]+=len(candidates)
            for item in candidates:
                pair,why=choose_match(item,approved)
                if pair is None:
                    count["unmatched_or_ambiguous"]+=1
                    continue
                count["matched"]+=1
                if not dry_run:
                    save_match(pair)
                    count["submitted"]+=1
            print("Government/OSM crosscheck:",source["source_key"],
                  "official",len(approved),"OSM nearby",len(candidates))
        except Exception as exc:
            count["errors"]+=1
            print("GIS-OSM crosscheck held:",source.get("source_key"),
                  type(exc).__name__,str(exc)[:180])
    for key in ("official_points","candidate_points","matched",
                "submitted","unmatched_or_ambiguous","errors"):
        print("Independent camera match",key+":",count[key])
    print("Additional public camera pins published by matcher: 0")
    return count


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run",action="store_true")
    import sys
    result=run(dry_run=ap.parse_args().dry_run)
    if result["errors"]: sys.exit("Independent source matching unavailable for some verified GIS sources")
