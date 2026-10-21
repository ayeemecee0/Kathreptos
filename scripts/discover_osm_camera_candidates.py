"""Nationwide Flock-tagged OSM camera candidate collector (PRIVATE QUEUE ONLY).

Data: community OpenStreetMap tags, redistributed by FlockHopper
(ODbL attribution). A community tag is NOT independent confirmation that
Flock operates a camera. Nothing here writes public camera-location tables.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import urllib.request
from collections import Counter

import ijson
from auto_verify_flock_agenda import api_request

DATA_URL="https://data.dontgetflocked.com/cameras.geojson.gz"
MAX_BYTES=48*1024*1024
MAX_FEATURES=220_000
MAX_CANDIDATES_PER_RUN=3300
SHARDS=30
BATCH_SIZE=100
ALLOWED_VENDORS=frozenset(("flock","flock safety","flock safety inc","flock safety, inc."))

class LimitedReader:
    """Cap compressed bytes before gzip/ijson decoding."""
    def __init__(self,raw,max_bytes=MAX_BYTES):
        self.raw=raw
        self.remaining=max_bytes
    def read(self,size=-1):
        if self.remaining<=0:
            raise ValueError("Compressed OSM dataset exceeded size limit")
        if size<0 or size>self.remaining:
            size=self.remaining+1
        data=self.raw.read(size)
        self.remaining-=len(data)
        if self.remaining<0:
            raise ValueError("Compressed OSM dataset exceeded size limit")
        return data

class PrefixReader:
    """Allow sniffing gzip magic without dropping bytes from streamed JSON."""
    def __init__(self, prefix, stream):
        self.prefix=prefix
        self.stream=stream
    def read(self, size=-1):
        if size is None or size<0:
            v=self.prefix
            self.prefix=b""
            return v+self.stream.read()
        a=self.prefix[:size]
        self.prefix=self.prefix[size:]
        if len(a)==size:
            return a
        return a+self.stream.read(size-len(a))


def parse_data_stream(raw):
    first=raw.read(2)
    if first==b"\x1f\x8b":
        decoded=gzip.GzipFile(fileobj=PrefixReader(first,raw))
        # Decompressed data is bounded separately from compressed bytes.
        stream=LimitedReader(decoded,160*1024*1024)
    elif first in (b'{"',b'{\n',b'{ ',b'{\r',b'{\t'):
        stream=PrefixReader(first,raw)
    else:
        raise ValueError("Unrecognized OSM GeoJSON encoding")
    return ijson.items(stream,"features.item")


def candidate_from_feature(feature):
    if not isinstance(feature,dict) or feature.get("type")!="Feature":
        return None
    geom=feature.get("geometry")
    p=feature.get("properties")
    if not isinstance(geom,dict) or not isinstance(p,dict):
        return None
    if geom.get("type")!="Point":
        return None
    raw_id=p.get("osmId")
    kind=p.get("osmType")
    if type(raw_id) is not int or raw_id<=0 or kind!="node":
        # OSM ways are centroid representations, not exact camera points.
        return None
    vendor=str(p.get("brand") or "").strip()
    if vendor.casefold() not in ALLOWED_VENDORS:
        return None
    coords=geom.get("coordinates")
    if not isinstance(coords,list) or len(coords)!=2:
        return None
    try:
        longitude=float(coords[0]);latitude=float(coords[1])
    except (TypeError,ValueError,OverflowError):
        return None
    if not (17<=latitude<=72 and -180<=longitude<=-64):
        return None
    if not all(abs(x)<float("inf") for x in (latitude,longitude)):
        return None
    latitude=round(latitude,7);longitude=round(longitude,7)
    key="osm:node:"+str(raw_id)
    summary=(f"Uncorroborated OpenStreetMap ALPR point node {raw_id}, tagged "
             f"brand={vendor!r}; distributed by public FlockHopper/DeFlock data. "
             "Community attribution is NOT proof of current Flock ownership or operation.")
    canon=json.dumps({"osm":key,"latitude":latitude,"longitude":longitude,
                      "brand":vendor},sort_keys=True,separators=(',',':'))
    return {
        "candidate_key":key,
        "source_kind":"osm_public_dataset",
        "source_url":"https://www.openstreetmap.org/node/"+str(raw_id),
        "source_external_id":str(raw_id),
        "latitude":latitude,
        "longitude":longitude,
        "declared_vendor":"Flock Safety",
        "evidence_excerpt":summary[:700],
        "evidence_fingerprint":hashlib.sha256(canon.encode()).hexdigest(),
    }

def upload_batch(batch):
    if not batch:
        return 0
    result=api_request(
        "flock_camera_discovery_candidates?on_conflict=candidate_key",
        method="POST",payload=batch,
        prefer="resolution=ignore-duplicates,return=representation")
    if not isinstance(result,list) or len(result)>len(batch):
        raise ValueError("Unexpected candidate queue insertion receipt")
    return len(result)

def scan_features(features,shard,dry_run=False):
    if type(shard) is not int or not 0<=shard<SHARDS:
        raise ValueError("Shard outside expected range")
    counts=Counter();selected=[]
    for f in features:
        counts["seen"]+=1
        if counts["seen"]>MAX_FEATURES:
            raise ValueError("OSM source feature bound exceeded")
        item=candidate_from_feature(f)
        if item is None:
            continue
        counts["flock_tagged"]+=1
        node_id=int(item["source_external_id"])
        if node_id%SHARDS!=shard:
            continue
        counts["shard_matched"]+=1
        if counts["staged"]>=MAX_CANDIDATES_PER_RUN:
            continue
        selected.append(item);counts["staged"]+=1
    # Validate source completeness BEFORE any database mutation.
    if counts["seen"]<50_000:
        raise ValueError("Nationwide community dataset truncated or below integrity floor")
    if not dry_run:
        for offset in range(0,len(selected),BATCH_SIZE):
            counts["inserted"]+=upload_batch(selected[offset:offset+BATCH_SIZE])
    for key in ("seen","flock_tagged","shard_matched","staged","inserted"):
        print("OSM community candidates",key+":",counts[key])
    print("Verified government camera locations published from OSM candidate data: 0")
    return counts

def scan(dry_run=False,shard=None):
    if shard is None:
        shard=dt.date.today().toordinal()%SHARDS
    req=urllib.request.Request(
        DATA_URL,headers={
          "User-Agent":"Katoptron/1.0 civic camera transparency",
          "Accept":"application/gzip,application/octet-stream",
        })
    with urllib.request.urlopen(req,timeout=35) as response:
        if response.geturl()!=DATA_URL:
            raise ValueError("Community OSM source redirected to unapproved host")
        raw=LimitedReader(response)
        return scan_features(parse_data_stream(raw),shard,dry_run=dry_run)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--shard",type=int,help="0–29; current day shard by default")
    args=parser.parse_args()
    scan(dry_run=args.dry_run,shard=args.shard)
