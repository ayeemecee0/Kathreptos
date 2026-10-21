"""Discover possible Flock municipal GIS layers, without granting them authority.

An ArcGIS hosted layer's title cannot prove it belongs to a government or
depicts installed equipment. Each discovered layer remains a PRIVATE
unverified source candidate until a stronger original-government source link
can be independently established. All fetch targets are static allowlisted.
"""
import argparse
import re
import urllib.request
from collections import Counter

from auto_verify_flock_agenda import api_request
from auto_verify_camera_gis import get_official_json

SEEDS = (
    {
        "url": "https://services3.arcgis.com/0m9qmmEbiydeqFeD/ArcGIS/rest/services/Flock_Cameras/FeatureServer/0",
        "context": "https://agenda.savannahga.gov/publishing/december-11-2025-city-council-regular-meeting/1537_11875.html",
    },
    {
        "url": "https://services3.arcgis.com/0m9qmmEbiydeqFeD/ArcGIS/rest/services/Flock_Camera_Locations2/FeatureServer/0",
        "context": "https://agenda.savannahga.gov/publishing/december-11-2025-city-council-regular-meeting/1537_11875.html",
    },
    {
        "url": "https://services.arcgis.com/su8ic9KbA7PYVxPS/arcgis/rest/services/Cloverleaf_WFL1/FeatureServer/1",
        "context": None,
    },
)
METADATA_MAX_FIELDS = 80
ALLOWED_IDS = frozenset("OBJECTID OBJECTID_1 FID".split())


def candidate_from_metadata(seed, metadata):
    if seed not in SEEDS:
        raise ValueError("Only pinned, inspectable GIS hosts may be fetched")
    if not isinstance(metadata, dict) or metadata.get("error"):
        raise ValueError("Missing or rejected GIS metadata")
    name = metadata.get("name")
    geometry = metadata.get("geometryType")
    layer_type = metadata.get("type")
    oid = metadata.get("objectIdField")
    fields = metadata.get("fields")
    if not isinstance(name,str) or not re.search(r"\bflock\b",name,re.I):
        raise ValueError("GIS layer title does not identify Flock cameras")
    if len(name)>180 or geometry != "esriGeometryPoint" or layer_type != "Feature Layer":
        raise ValueError("GIS metadata is not a point feature layer")
    if not isinstance(fields,list) or len(fields)>METADATA_MAX_FIELDS:
        raise ValueError("Missing or oversized GIS field metadata")
    if oid not in ALLOWED_IDS or not any(
        f.get("name")==oid and f.get("type")=="esriFieldTypeOID"
        for f in fields if isinstance(f,dict)):
        raise ValueError("GIS ID field missing or not a real object ID")
    return {
        "gis_layer_url": seed["url"],
        "layer_name": name,
        "geometry_type": geometry,
        "object_id_field": oid,
        "layer_purpose": (
            "Unverified third-party hosted point layer whose title explicitly mentions Flock. "
            "Government Flock procurement, if separately documented, does NOT establish "
            "who operates or uploaded this ArcGIS layer or whether any coordinates are correct."),
        "public_gov_context_url": seed["context"],
        "trust_status": "unverified",
    }


def stage_candidate(candidate):
    receipt=api_request(
        "flock_gis_source_candidates?on_conflict=gis_layer_url",
        method="POST",payload=[candidate],
        prefer="resolution=ignore-duplicates,return=minimal")
    if receipt is not None:
        raise ValueError("Unexpected GIS source candidate staging receipt")


def scan(dry_run=False):
    counts=Counter()
    for seed in SEEDS:
        url=seed["url"]
        try:
            metadata=get_official_json(url+"?f=json")
            item=candidate_from_metadata(seed,metadata)
            counts["qualified_leads"]+=1
            if not dry_run:
                stage_candidate(item)
                counts["submitted"]+=1
            print("Private GIS source candidate:",item["layer_name"],url)
        except Exception as exc:
            counts["held"]+=1
            print("GIS source candidate held:",url,type(exc).__name__,str(exc)[:180])
    for k in ("qualified_leads","submitted","held"):
        print("Potential GIS source",k+":",counts[k])
    print("Government GIS authorities auto-approved: 0")
    return counts


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run",action="store_true")
    scan(dry_run=ap.parse_args().dry_run)
