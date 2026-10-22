"""Publish ONLY exact original-government Flock deployment polygon geometry.

A program contract does not imply a map footprint. Only government-owned GIS
services already tied to reviewed source authority are scanned. Polygons
must carry original Flock-specific layer names and bounded point coordinates.
No city centroid circles or hypothetical coverage extents are generated.
"""
import argparse
import hashlib
import json
import re
import urllib.parse
from collections import Counter

from auto_verify_flock_agenda import api_request
from auto_verify_camera_gis import get_official_json

POLYGON=re.compile(
    r"^flock[ _-]+(?:safety[ _-]+)?(?:camera[ _-]+)?"
    r"(?:deployment|coverage)[ _-]+areas?$",re.I)
LIMIT=51


def approved_hosts():
    roots=api_request("gis_government_host_authorities?select=authority_key,"
       "government_gis_host,allowed_layer_path,verification_status"
       "&verification_status=eq.verified&limit=100")
    if not isinstance(roots,list) or len(roots)>=100:
        raise ValueError("Approved original government GIS host list incomplete")
    return roots


def polygon_layers(root):
    if root.get("verification_status")!="verified":
        raise ValueError("Original government host no longer verified")
    host=root["government_gis_host"]
    path=root["allowed_layer_path"]
    if (not re.fullmatch(r"[a-z0-9.-]+",host) or
        not re.fullmatch(r"/[A-Za-z0-9_/-]+/(?:MapServer|FeatureServer)/[0-9]+",path)):
        raise ValueError("Invalid reviewed GIS original layer binding")
    service_url=("https://"+host+path).rsplit("/",1)[0]
    service=get_official_json(service_url+"?f=json")
    items=service.get("layers") if isinstance(service,dict) else None
    if not isinstance(items,list) or len(items)>300:
        raise ValueError("Original government GIS service catalog absent")
    for item in items:
        if not isinstance(item,dict):continue
        oid,name=item.get("id"),item.get("name")
        if type(oid) is int and 0<=oid<1000 and isinstance(name,str) and POLYGON.fullmatch(name):
            yield service_url+"/"+str(oid),name


def verify_polygon(root,url,label):
    layer=get_official_json(url+"?f=json")
    if (not isinstance(layer,dict) or layer.get("error") or
        layer.get("name")!=label or layer.get("type")!="Feature Layer" or
        layer.get("geometryType")!="esriGeometryPolygon"):
        raise ValueError("Government GIS layer not a Flock deployment polygon")
    fields=layer.get("fields")
    if not isinstance(fields,list) or len(fields)>140:
        raise ValueError("Invalid official polygon metadata")
    oid=layer.get("objectIdField") or "OBJECTID"
    if not any(isinstance(f,dict) and f.get("name")==oid and
               f.get("type")=="esriFieldTypeOID" for f in fields):
        raise ValueError("Original polygon has no persistent feature ID")
    query=urllib.parse.urlencode({
       "where":"1=1","outFields":oid,"returnGeometry":"true",
       "outSR":"4326","resultRecordCount":LIMIT,"f":"json"
    })
    data=get_official_json(url+"/query?"+query)
    features=data.get("features") if isinstance(data,dict) else None
    if (not isinstance(features,list) or not 1<=len(features)<LIMIT
        or data.get("error") or data.get("exceededTransferLimit")):
        raise ValueError("Government polygon dataset missing or incomplete")
    results=[];seen=set()
    for feature in features:
        attributes=feature.get("attributes") if isinstance(feature,dict) else None
        geom=feature.get("geometry") if isinstance(feature,dict) else None
        if not isinstance(attributes,dict) or not isinstance(geom,dict):
            raise ValueError("Original government polygon record malformed")
        objectid=attributes.get(oid)
        rings=geom.get("rings")
        if type(objectid) is not int or objectid<=0 or objectid in seen:
            raise ValueError("Government polygon identifier missing or duplicate")
        seen.add(objectid)
        # Multi-part areas / holes require explicit GeoJSON topology
        # translation; hold them rather than accidentally filling holes.
        if not isinstance(rings,list) or len(rings)!=1:
            raise ValueError("Polygon contains ambiguous multipart geometry")
        ring=rings[0]
        if not isinstance(ring,list) or not 4<=len(ring)<=250 or ring[0]!=ring[-1]:
            raise ValueError("Official area ring invalid or unclosed")
        for pair in ring:
            if (not isinstance(pair,list) or len(pair)!=2 or
                type(pair[0]) not in (int,float) or
                type(pair[1]) not in (int,float) or
                not -180<=pair[0]<=-64 or not 17<=pair[1]<=72):
                raise ValueError("Original polygon coordinates invalid")
        proof=hashlib.sha256(json.dumps(
            {"source":url,"id":objectid,"ring":ring},sort_keys=True
        ).encode()).hexdigest()
        results.append({
          "p_source_key":root["authority_key"],
          "p_area_key":"area_"+proof[:24],
          "p_label":f"Flock deployment area · Government GIS #{objectid}",
          "p_evidence_url":url,
          "p_evidence_sha":proof,
          "p_outline":ring
        })
    return results


def run(dry_run=False):
    stats=Counter();seen=set()
    for root in approved_hosts():
        try:
            for layer_url,name in polygon_layers(root):
                if layer_url in seen:continue
                seen.add(layer_url)
                try:
                    proofs=verify_polygon(root,layer_url,name)
                    stats["original_gis_areas_qualified"]+=len(proofs)
                    for proof in proofs:
                        if not dry_run:
                            ok=api_request("rpc/register_original_government_flock_area",
                              method="POST",payload=proof)
                            if ok is not True:
                                raise ValueError("Database rejected original polygon verification")
                            stats["verified_areas_submitted"]+=1
                except Exception as ex:
                    stats["area_layers_held"]+=1
                    print("Government Flock area withheld:",type(ex).__name__,str(ex)[:150])
            stats["original_government_hosts_checked"]+=1
        except Exception as ex:
            stats["host_errors"]+=1
            print("Government polygon source host held:",root.get("authority_key"),
                  type(ex).__name__,str(ex)[:180])
    for key in ("original_government_hosts_checked","original_gis_areas_qualified",
                "verified_areas_submitted","area_layers_held","host_errors"):
        print("Original Flock coverage",key+":",stats[key])
    print("Deployment polygons invented from agency programs or city centroids: 0")
    return stats


if __name__=="__main__":
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--dry-run",action="store_true")
    o=run(arg.parse_args().dry_run)
    if o["host_errors"]:
        raise SystemExit("Original government GIS polygon discovery incomplete")
