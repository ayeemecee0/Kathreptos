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
import time
import math
import urllib.error
import socket
from collections import Counter

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from paged_supabase import fetch_all
from auto_verify_camera_gis import (
    get_official_json, classify_camera_type, write_verified,
    mark_rechecked, revoke_stale
)

LIMIT=1000
PAGE_SIZE=150
MAX_SOURCE_FEATURES=3000
FIELD=re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,50}$")
FLOCK_LAYER=re.compile(r"^(?:flock[_ ]cameras(?: - [A-Za-z][A-Za-z ]{0,60})?|flock unit locations)$",re.I)
ORIGINAL_OBJECT_ID=re.compile(r"^objectid(?:_[0-9]+)?$",re.I)


def approved_sources():
    src=fetch_all(api_request,"trusted_flock_gis_sources?select=source_key,gis_layer_url,"
        "government_evidence_url,jurisdiction_label,expected_id_field,"
        "bounds_south,bounds_west,bounds_north,bounds_east,source_status"
        "&source_status=eq.verified&limit=100","source_key")
    policies=fetch_all(api_request,"gis_verification_profiles?select=source_key,"
        "expected_layer_name,identity_mode,vendor_field,camera_id_field,"
        "service_evidence_mode,profile_status&profile_status=eq.verified&limit=100","source_key")
    roots=fetch_all(api_request,"gis_government_host_authorities?select=authority_key,"
        "government_gis_host,official_government_page,allowed_layer_path,"
        "jurisdiction_label,verification_status&verification_status=eq.verified&limit=100","authority_key")
    external=fetch_all(api_request,"official_external_flock_gis_authorities?select=source_key,"
        "parent_source_key,government_disclosure_url,gis_layer_url,"
        "verification_status&verification_status=eq.verified&limit=100","source_key")
    first_party_receipts=fetch_all(api_request,
        "first_party_agency_gis_receipts?select=source_key,agency_page_url,"
        "agency_portal_url,identity_basis&limit=100","source_key")
    reviewed_first_party=fetch_all(api_request,
        "reviewed_first_party_gis_roots?select=source_key,agency_page_url,"
        "agency_portal_url,gis_layer_url,jurisdiction_label,review_status"
        "&review_status=eq.verified&limit=100","source_key")
    # Every approved registry is now read fully, or fails closed on cap/error.
    ps={x["source_key"]:x for x in policies}
    rs={x["authority_key"]:x for x in roots}
    by_key={x["source_key"]:x for x in src}
    es={x["source_key"]:x for x in external}
    first_by={x["source_key"]:x for x in first_party_receipts}
    reviewed_by={x["source_key"]:x for x in reviewed_first_party}
    checked=[]
    for source in src:
        policy=ps.get(source["source_key"])
        if not policy:
            raise ValueError("Verified government source has no owner-approved GIS policy")
        endorsement=es.get(source["source_key"])
        if endorsement:
            parent=by_key.get(endorsement["parent_source_key"])
            root=rs.get(endorsement["parent_source_key"])
            if (not parent or not root or
                parent["source_status"]!="verified" or
                parent["gis_layer_url"]!="https://"+root["government_gis_host"]+
                  root["allowed_layer_path"] or
                parent["government_evidence_url"]!=root["official_government_page"] or
                parent["jurisdiction_label"]!=root["jurisdiction_label"] or
                source["jurisdiction_label"]!=parent["jurisdiction_label"] or
                source["government_evidence_url"]!=root["official_government_page"]):
                raise ValueError("External GIS endorsement lost its original government parent")
            # This changes evidence copy, not which database authority or
            # original GIS source can authorize publication.
            source={**source,"government_endorsed_external":True}
        original_receipt=first_by.get(source["source_key"])
        if original_receipt:
            reviewed=reviewed_by.get(source["source_key"])
            if (not reviewed or reviewed["review_status"]!="verified"
                or original_receipt["agency_page_url"]!=reviewed["agency_page_url"]
                or original_receipt["agency_portal_url"]!=reviewed["agency_portal_url"]
                or source["government_evidence_url"]!=reviewed["agency_page_url"]
                or source["gis_layer_url"]!=reviewed["gis_layer_url"]
                or source["jurisdiction_label"]!=reviewed["jurisdiction_label"]
                or not rs.get(source["source_key"])):
                raise ValueError("First-party government GIS receipt lost independent reviewed source binding")
            source={**source,"reviewed_first_party_receipt":True}
        authorize(source,policy,rs.get(source["source_key"]),endorsement)
        checked.append((source,policy))
    return checked


def authorize(s,p,r,external=None):
    if (s.get("source_status")!="verified" or p.get("profile_status")!="verified"
        or p.get("source_key")!=s.get("source_key") or
        not ORIGINAL_OBJECT_ID.fullmatch(s.get("expected_id_field") or "")):
        raise ValueError("GIS authority not independently verified")
    a=urllib.parse.urlsplit(s.get("gis_layer_url") or "")
    b=urllib.parse.urlsplit(s.get("government_evidence_url") or "")
    if (a.scheme!="https" or b.scheme!="https" or a.username or a.password or
        b.username or b.password or a.port not in (None,443) or
        b.port not in (None,443) or a.query or a.fragment or
        not re.fullmatch(r"/.+/(MapServer|FeatureServer)/\d+",a.path)):
        raise ValueError("Unverified government GIS URL")
    if r:
        if r.get("authority_key")!=s.get("source_key"):
            raise ValueError("First-party GIS receipt and independently reviewed root source keys disagree")
        if (r.get("verification_status")!="verified" or
            s["gis_layer_url"]!="https://"+r["government_gis_host"]+r["allowed_layer_path"] or
            s["government_evidence_url"]!=r["official_government_page"] or
            s["jurisdiction_label"]!=r["jurisdiction_label"]):
            raise ValueError("GIS URL/authority differs from owner-reviewed government root")
    elif external:
        if (external.get("verification_status")!="verified" or
            external.get("source_key")!=s.get("source_key") or
            external.get("gis_layer_url")!=s.get("gis_layer_url") or
            external.get("government_disclosure_url")!=s.get("government_evidence_url") or
            not re.fullmatch(
              r"services[0-9]*\.arcgis\.com",a.hostname or "") or
            not re.fullmatch(r"/[A-Za-z0-9]+/arcgis/rest/services/"
              r"[A-Za-z0-9_-]+/FeatureServer/[0-9]+",a.path)):
            raise ValueError("Original government-endorsed Esri source lost exact authority")
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
        if ((p.get("camera_id_field") or "").lower()==
            (s.get("expected_id_field") or "").lower() and
            not s.get("reviewed_first_party_receipt")):
            raise ValueError("Typed ObjectID-only camera identities require vetted first-party agency receipt")
        if (not (r or external) or not FLOCK_LAYER.fullmatch(p.get("expected_layer_name") or "") or
            not FIELD.fullmatch(p.get("camera_id_field") or "") or
            (p.get("vendor_field") is not None and not FIELD.fullmatch(p["vendor_field"])) or
            p.get("service_evidence_mode") not in
              ("listed_flock_layer","explicit_flock_service_text")):
            raise ValueError("Unapproved government layer-name Flock attribution")
        if (p.get("expected_layer_name","").lower()=="flock unit locations" and
            (not r or p.get("service_evidence_mode")!="listed_flock_layer")):
            raise ValueError("Flock unit-list attribution requires exact reviewed government GIS root")
    else:
        raise ValueError("Unsupported GIS identity policy")
    return True


def original_object_id_field(fields):
    """Canonical OID must be an ArcGIS OID, not an arbitrary permit number.

    Preserve a consistent internal OBJECTID while accepting common original
    ArcGIS capitalization differences (OBJECTID / objectid / ObjectID).
    """
    if not isinstance(fields,list):
        return None
    candidates=[f.get("name") for f in fields if isinstance(f,dict)
       and ORIGINAL_OBJECT_ID.fullmatch(str(f.get("name") or ""))
       and f.get("type")=="esriFieldTypeOID"]
    return candidates[0] if len(candidates)==1 else None


def check_metadata(s,p,service,layer):
    if (not isinstance(service,dict) or not isinstance(layer,dict) or
        service.get("error") or layer.get("error") or
        layer.get("type")!="Feature Layer" or layer.get("geometryType")!="esriGeometryPoint"):
        raise ValueError("Original government GIS point metadata missing")
    fields=layer.get("fields")
    if not isinstance(fields,list) or not 1<=len(fields)<=140:
        raise ValueError("Malformed government GIS fields")
    names={f.get("name") for f in fields if isinstance(f,dict)}
    actual_oid=original_object_id_field(fields)
    if not actual_oid or actual_oid.lower()!=s["expected_id_field"].lower():
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


def resilient_government_gis_json(url):
    """Retry ONE transient timeout; permanent errors still fail closed."""
    for attempt in range(2):
        try:
            return get_official_json(url)
        except (TimeoutError, ConnectionResetError, ConnectionAbortedError):
            if attempt:
                raise
            time.sleep(0.35)


def query_gis(s,p):
    """Read a COMPLETE bounded ArcGIS inventory by canonical ObjectIDs.

    ArcGIS may silently enforce smaller service-specific page sizes. First
    request the authoritative ID list, fetch exactly those IDs in chunks,
    and re-fetch the ID list afterward. Any missing/duplicate/changed ID
    prevents reconciliation; a partial response can never revoke cameras.
    """
    parent=s["gis_layer_url"].rsplit("/",1)[0]
    service=resilient_government_gis_json(parent+"?f=json")
    layer=resilient_government_gis_json(s["gis_layer_url"]+"?f=json")
    check_metadata(s,p,service,layer)
    oid_field=original_object_id_field(layer["fields"])
    fields=[oid_field]
    if p["identity_mode"]=="per_feature_vendor":
        fields.append(p["vendor_field"])
    else:
        fields.append(p["camera_id_field"])
        if p.get("vendor_field"):fields.append(p["vendor_field"])
    # A first-party government Flock source may use its typed original
    # objectid as its only per-camera identifier. Do not request the same
    # ArcGIS field twice when it is both ObjectID and camera ID.
    fields=list(dict.fromkeys(fields))
    url=s["gis_layer_url"]+"/query?"
    def read_ids():
        q=urllib.parse.urlencode({"where":"1=1","returnIdsOnly":"true","f":"json"})
        response=resilient_government_gis_json(url+q)
        if not isinstance(response,dict) or response.get("error"):
            raise ValueError("Original GIS full ObjectID inventory unavailable")
        ids=response.get("objectIds")
        field=response.get("objectIdFieldName")
        if (not isinstance(field,str) or field.lower()!=oid_field.lower()
            or not isinstance(ids,list) or not 1<=len(ids)<=MAX_SOURCE_FEATURES
            or any(type(x) is not int or x<=0 for x in ids)
            or len(ids)!=len(set(ids))):
            raise ValueError("Original GIS identity set empty, oversized or malformed")
        return sorted(ids)
    original=read_ids()
    all_features=[]
    for offset in range(0,len(original),PAGE_SIZE):
        group=original[offset:offset+PAGE_SIZE]
        q=urllib.parse.urlencode({
          "objectIds":",".join(map(str,group)),
          "outFields":",".join(sorted(set(fields))),
          "returnGeometry":"true","outSR":"4326","f":"json"
        })
        result=resilient_government_gis_json(url+q)
        if (not isinstance(result,dict) or result.get("error")
            or result.get("exceededTransferLimit")
            or not isinstance(result.get("features"),list)):
            raise ValueError("Original GIS ObjectID page malformed or truncated")
        features=result["features"]
        observed=[]
        for entry in features:
            attrs=entry.get("attributes") if isinstance(entry,dict) else None
            if not isinstance(attrs,dict):
                raise ValueError("Original GIS ObjectID page contains malformed feature")
            found=[v for k,v in attrs.items()
                   if isinstance(k,str) and k.lower()==oid_field.lower()]
            if len(found)!=1 or type(found[0]) is not int:
                raise ValueError("Original GIS ObjectID page lacks stable identifiers")
            observed.append(found[0])
        if len(observed)!=len(group) or sorted(observed)!=group:
            raise ValueError("Original GIS ObjectID page omitted/duplicated features")
        all_features.extend(features)
    if read_ids()!=original:
        raise ValueError("Original GIS inventory changed during source verification")
    if len(all_features)!=len(original):
        raise ValueError("Original GIS inventory incomplete after pagination")
    return {"features":all_features}


def verify_points(s,p,data):
    if (not isinstance(data,dict) or data.get("error") or
        not isinstance(data.get("features"),list) or
        not 1<=len(data["features"])<=MAX_SOURCE_FEATURES or data.get("exceededTransferLimit")):
        raise ValueError("Official GIS data empty, malformed or truncated")
    records=[];holds=Counter();ids=set()
    south,west,north,east=[s[k] for k in ("bounds_south","bounds_west","bounds_north","bounds_east")]
    for f in data["features"]:
        a=f.get("attributes") if isinstance(f,dict) else None
        g=f.get("geometry") if isinstance(f,dict) else None
        if not isinstance(a,dict) or not isinstance(g,dict):
            holds["missing GIS fields or geometry"]+=1;continue
        oid_values=[v for k,v in a.items() if isinstance(k,str)
                    and k.lower()==s["expected_id_field"].lower()]
        oid=oid_values[0] if len(oid_values)==1 else None
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
            if (s.get("reviewed_first_party_receipt") and
                p["camera_id_field"].lower()==s["expected_id_field"].lower()):
                # An agency-operated Flock-only layer can use its typed,
                # twice-rechecked original ArcGIS ObjectID as the individual
                # feature identity. This narrow exception cannot be used by
                # arbitrary third-party map candidates.
                if type(identifier) is not int or identifier!=oid:
                    holds["original agency ObjectID changed"]+=1;continue
            elif not isinstance(identifier,str) or not 1<=len(identifier.strip())<=100:
                holds["no individual camera identifier"]+=1;continue
            # A mixed government point layer may include school/traffic
            # equipment. Filter each feature if an additional reviewed
            # per-camera manufacturer/type field is defined.
            if p.get("vendor_field") and not classify_camera_type(a.get(p["vendor_field"])):
                holds["not a Flock camera per original GIS field"]+=1;continue
            # Preserve earlier evidence fingerprints for unchanged published
            # sources, avoiding fictitious withdrawal/republication history.
            if s["source_key"].startswith("autogov_") or s.get("reviewed_first_party_receipt"):
                camera_type="Flock (original government-hosted GIS camera layer)"
            elif p.get("expected_layer_name","").lower()=="flock unit locations":
                camera_type="Flock (original city Police GIS unit layer)"
            elif s.get("government_endorsed_external"):
                camera_type="Flock (original government-endorsed external GIS layer)"
            else:
                # Preserve original evidence fingerprints for the already
                # published municipal sources, avoiding phantom withdrawals.
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
          "evidence_summary":(
             ("Original government-endorsed, independently ArcGIS-hosted Flock camera data: "
              if s.get("government_endorsed_external")
              else "Official government point camera source: ")+
             camera_type+". Exact GIS location and Flock identification are source-backed; "
             "hosting ownership and device uptime/plate readings are not established."),
          "evidence_sha256":digest,
          "verification_method":"official_georeferenced_camera_record_v1",
          "last_confirmed_on":dt.date.today().isoformat()
        })
    return records,holds,len(data["features"])


def fetch_existing(prefix):
    """Page the full verified inventory belonging to one reviewed source."""
    if not isinstance(prefix,str) or not re.fullmatch(r"gis-[a-zA-Z0-9_-]{2,90}-",prefix):
        raise ValueError("Untrusted existing-camera source prefix")
    # SQL LIKE treats '_' as a one-character wildcard; never allow
    # one municipality's source key to match another verified source.
    escaped=prefix.replace("_",r"\_")
    qs=urllib.parse.urlencode({
      "select":"record_key,verification_status",
      "record_key":"like."+escaped+"*",
      "verification_status":"eq.verified"})
    rows=fetch_all(api_request,"flock_camera_locations?"+qs,
      "record_key",page_size=50,max_records=MAX_SOURCE_FEATURES+100)
    if any(not isinstance(r,dict) or
           not isinstance(r.get("record_key"),str) or
           not r["record_key"].startswith(prefix) or
           r.get("verification_status")!="verified" for r in rows):
        raise ValueError("Existing camera query crossed a reviewed source boundary")
    return rows


def validate_reconciliation_delta(previous,new_keys):
    """Withhold sudden large removals before any publication mutations."""
    if not isinstance(previous,list) or not isinstance(new_keys,set):
        raise ValueError("Government camera delta inputs malformed")
    old_keys={item.get("record_key") for item in previous}
    if len(old_keys)!=len(previous) or None in old_keys:
        raise ValueError("Existing government camera source record IDs incomplete")
    removed=old_keys-new_keys
    if previous and len(removed)>=max(3,math.ceil(len(previous)*0.25)):
        raise ValueError("Unexpectedly large government camera removal or movement: "+
                         str(len(removed))+" of "+str(len(previous))+
                         ". Hold until original data change is independently confirmed")
    return removed


def confirm_time_separated_withdrawals(source_key, missing_keys):
    """Two independently completed government inventories >=12h apart.

    Call even when the new inventory has no missing points, so a previously
    disappeared pin that reappeared has its private withdrawal hold cleared.
    The database verifies the exact reviewed source, individual published
    record identities and observation interval; the browser never sees
    unconfirmed withdrawals.
    """
    if (not isinstance(source_key,str) or
        not re.fullmatch(r"[a-z0-9_]{2,90}",source_key) or
        not isinstance(missing_keys,set) or len(missing_keys)>3000 or
        any(not isinstance(k,str) or not k.startswith("gis-"+source_key+"-")
            for k in missing_keys)):
        raise ValueError("Invalid source-specific missing camera inventory")
    response=api_request("rpc/confirm_gis_camera_withdrawals",
        method="POST",payload={"p_source_key":source_key,
                               "p_missing_keys":sorted(missing_keys)})
    if (not isinstance(response,dict) or
        not isinstance(response.get("confirmed"),list) or
        type(response.get("pending")) is not int or response["pending"]<0 or
        any(not isinstance(k,str) for k in response["confirmed"])):
        raise ValueError("Government camera withdrawal confirmation missing")
    approved=set(response["confirmed"])
    if (len(approved)!=len(response["confirmed"]) or
        not approved.issubset(missing_keys) or
        len(approved)+response["pending"]!=len(missing_keys)):
        raise ValueError("Government camera withdrawal confirmation inconsistent")
    return approved,response["pending"]


PUBLISH_BATCH_SIZE=25


def publish_verified_batches(rows,withdrawn):
    """Publish complete verified-source inventory with auditable small batches.

    Only record_keys from independently verified camera points may be passed.
    Every API receipt is checked against the exact requested key set.
    """
    if (not isinstance(rows,list) or not isinstance(withdrawn,set)
        or not rows or len(rows)>MAX_SOURCE_FEATURES):
        raise ValueError("Invalid bounded government camera publication batch")
    keys=[r.get("record_key") if isinstance(r,dict) else None for r in rows]
    if (any(not isinstance(key,str) or not re.fullmatch(r"gis-[a-zA-Z0-9_-]+",key)
            for key in keys) or len(set(keys))!=len(keys) or
        any(not isinstance(k,str) or not re.fullmatch(r"gis-[a-zA-Z0-9_-]+",k)
            for k in withdrawn) or set(keys)&withdrawn):
        raise ValueError("Camera evidence keys are malformed, duplicate or conflicting")
    from urllib.parse import urlencode
    counter=Counter()
    def receipt_keys(payload,expected):
        if (not isinstance(payload,list) or
            any(not isinstance(x,dict) or not isinstance(x.get("record_key"),str)
                for x in payload)):
            raise ValueError("Camera database returned malformed mutation receipt")
        seen=[x["record_key"] for x in payload]
        if len(seen)!=len(set(seen)) or not set(seen).issubset(expected):
            raise ValueError("Camera database returned unexpected mutation receipt")
        return set(seen)
    for offset in range(0,len(rows),PUBLISH_BATCH_SIZE):
        page=rows[offset:offset+PUBLISH_BATCH_SIZE]
        group={r["record_key"] for r in page}
        endpoint="flock_camera_locations?"+urlencode({
            "select":"record_key","on_conflict":"record_key"})
        added=api_request(endpoint,method="POST",payload=page,
            prefer="resolution=ignore-duplicates,return=representation")
        new=receipt_keys(added,group)
        counter["published"]+=len(new)
        old=group-new
        if old:
            endpoint="flock_camera_locations?"+urlencode({
                "select":"record_key","record_key":"in.("+",".join(sorted(old))+")",
                "verification_status":"eq.verified"})
            updated=api_request(endpoint,method="PATCH",
                payload={"last_source_recheck_at":dt.datetime.now(dt.timezone.utc).isoformat()},
                prefer="return=representation")
            actual=receipt_keys(updated,old)
            if actual!=old:
                raise ValueError("Existing camera recheck skipped a verified record")
            counter["rechecked"]+=len(actual)
    for offset in range(0,len(withdrawn),PUBLISH_BATCH_SIZE):
        group=set(sorted(withdrawn)[offset:offset+PUBLISH_BATCH_SIZE])
        endpoint="flock_camera_locations?"+urlencode({
            "select":"record_key","record_key":"in.("+",".join(sorted(group))+")",
            "verification_status":"eq.verified"})
        revoked=api_request(endpoint,method="PATCH",
            payload={"verification_status":"revoked"},
            prefer="return=representation")
        actual=receipt_keys(revoked,group)
        if actual!=group:
            raise ValueError("Camera source withdrawal receipt incomplete")
        counter["withdrawn"]+=len(actual)
    return counter


def source_with_bounded_retries(s,p,attempts=3):
    """Retry temporary government-host outages without changing evidence rules.

    An empty/malformed response is never interpreted as camera removal.
    Permanent metadata or schema failures still fail closed and are reported.
    """
    last=None
    for attempt in range(attempts):
        try:
            return verify_points(s,p,query_gis(s,p))
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last=exc
            print("Temporary official GIS network failure",s["source_key"],
                  "attempt",attempt+1, type(exc).__name__)
        except ValueError as exc:
            # Empty feature results can be a temporary GIS service fault,
            # but are not proof that cameras have been removed.
            if not any(term in str(exc).lower() for term in
                       ("empty","zero features","truncated","malformed")):
                raise
            last=exc
            print("Official GIS incomplete response held",s["source_key"],
                  "attempt",attempt+1, str(exc)[:120])
        if attempt+1<attempts:
            time.sleep(2*(attempt+1))
    raise RuntimeError("Source unavailable after bounded retries; previous camera publication held") from last


def assigned_to_verification_shard(source_key,shard=0,shards=1):
    """Deterministically partition exact government sources, never cameras.

    Every source belongs to exactly one worker for the selected shard count.
    Every worker still independently reads the complete approved registry;
    no source can fall through a missing pagination page unnoticed.
    """
    if (type(shard) is not int or type(shards) is not int
        or not 1<=shards<=16 or not 0<=shard<shards):
        raise ValueError("Invalid GIS source verification shard")
    if not isinstance(source_key,str) or not source_key:
        raise ValueError("Missing approved GIS source identity")
    ordinal=int.from_bytes(hashlib.sha256(
        source_key.encode("utf8")).digest()[:8],"big")
    return ordinal%shards==shard


def sync(dry_run=False,shard=0,shards=1):
    # Validate shard bounds even if no approved sources exist.
    assigned_to_verification_shard("_source_partition_probe",shard,shards)
    total=Counter()
    for s,p in approved_sources():
        if not assigned_to_verification_shard(s["source_key"],shard,shards):
            continue
        total["sources_assigned"]+=1
        try:
            rows,held,n=source_with_bounded_retries(s,p)
            total["sources_checked"]+=1;total["features_checked"]+=n
            total["eligible"]+=len(rows)
            print("PROFILE GIS SOURCE:",s["source_key"],"features",n,
                  "verified",len(rows),"held",dict(held))
            if dry_run:continue
            if not rows:raise ValueError("Zero independently qualifying camera records; withholding reconciliation")
            old=fetch_existing("gis-"+s["source_key"]+"-")
            keys={r["record_key"] for r in rows}
            missing=validate_reconciliation_delta(old,keys)
            confirmed,pending=confirm_time_separated_withdrawals(
                s["source_key"],missing)
            total["pending_withdrawal"]+=pending
            total.update(publish_verified_batches(rows,confirmed))
        except Exception as exc:
            total["errors"]+=1
            print("PROFILE GIS HELD:",s["source_key"],type(exc).__name__,str(exc)[:180])
    print("PROFILE GIS shard",str(shard)+"/"+str(shards),
          "sources assigned:",total["sources_assigned"])
    for k in ("sources_checked","features_checked","eligible","published",
              "rechecked","withdrawn","pending_withdrawal","errors"):
        print("PROFILE GIS",k+":",total[k])
    return total


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    a.add_argument("--shard",type=int,default=0)
    a.add_argument("--shards",type=int,default=1)
    options=a.parse_args()
    result=sync(options.dry_run,options.shard,options.shards)
    if result["errors"]:raise SystemExit("Source-profile GIS verification failed")
