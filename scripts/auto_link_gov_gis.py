"""Promote candidate *government-hosted* Flock GIS layers after fresh proof checks.

Only DB-owner verified government host + exact GIS path bindings may be promoted
by narrowly scoped database RPC. Generic Esri-hosted community maps are excluded.
"""
import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser

from auto_verify_flock_agenda import api_request
from auto_verify_camera_gis import get_official_json

MAX_PAGE_BYTES=700_000
MAX_FEATURES=1000


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.strings=[]
        self.ignoring=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'):
            self.ignoring+=1
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript') and self.ignoring:
            self.ignoring-=1
    def handle_data(self, data):
        if not self.ignoring:
            self.strings.append(data)


def read_official_government_page(url,expected_host):
    parsed=urllib.parse.urlsplit(url)
    if (parsed.scheme!='https' or parsed.netloc!=expected_host or parsed.fragment or
            parsed.username or parsed.password or parsed.port):
        raise ValueError("Official government evidence page not on trusted host")
    req=urllib.request.Request(url,headers={"User-Agent":"Katoptron/1.0 public government records"})
    with urllib.request.urlopen(req,timeout=18) as res:
        if res.geturl()!=url:
            raise ValueError("Government evidence page redirected")
        body=res.read(MAX_PAGE_BYTES+1)
    if not body or len(body)>MAX_PAGE_BYTES:
        raise ValueError("Government evidence page inaccessible or oversized")
    parsed_html=Visible()
    parsed_html.feed(body.decode("utf8","replace"))
    visible=" ".join(parsed_html.strings).lower()
    if "el paso county" not in visible or "gis" not in visible:
        raise ValueError("Government proof does not identify county GIS function")
    return True


def get_source_candidates():
    sources=api_request(
        "trusted_flock_gis_sources?select=source_key,gis_layer_url,"
        "government_evidence_url,jurisdiction_label,expected_camera_type_field,"
        "expected_id_field,bounds_south,bounds_north,bounds_west,bounds_east,source_status"
        "&source_status=eq.candidate&limit=40")
    roots=api_request(
        "gis_government_host_authorities?select=authority_key,government_gis_host,"
        "official_government_page,jurisdiction_label,allowed_layer_path,"
        "expected_layer_name,bounds_south,bounds_north,bounds_west,bounds_east,"
        "verification_status&verification_status=eq.verified&limit=40")
    if not isinstance(sources,list) or not isinstance(roots,list) or len(sources)>=40 or len(roots)>=40:
        raise ValueError("Approved authority registry incomplete")
    roots={x["authority_key"]:x for x in roots}
    return [(s,roots[s["source_key"]]) for s in sources if s.get("source_key") in roots]


def ensure_authority(source,root):
    if source.get("source_status")!="candidate" or root.get("verification_status")!="verified":
        raise ValueError("Source and government host must have distinct eligible states")
    host=root.get("government_gis_host")
    page=root.get("official_government_page")
    path=root.get("allowed_layer_path")
    if not isinstance(host,str) or not isinstance(path,str) or not isinstance(page,str):
        raise ValueError("Malformed original government binding")
    if source.get("gis_layer_url")!="https://"+host+path:
        raise ValueError("GIS URL not identical to government-owner-approved exact layer")
    if source.get("government_evidence_url")!=page or source.get("jurisdiction_label")!=root.get("jurisdiction_label"):
        raise ValueError("County agency/source binding does not match")
    if source.get("expected_camera_type_field")!="FlockLayer" or source.get("expected_id_field")!="OBJECTID":
        raise ValueError("Unsupported GIS camera identification profile")
    for field in ("bounds_south","bounds_west","bounds_north","bounds_east"):
        if source.get(field)!=root.get(field):
            raise ValueError("Source coordinates do not match approved government boundaries")
    if root.get("expected_layer_name")!="Flock_Cameras":
        raise ValueError("Government layer identity is not the reviewed exact Flock layer")
    if host!="gisservices.elpasoco.com" or urllib.parse.urlsplit(page).hostname!="admin.elpasoco.com":
        raise ValueError("Government network not on independently reviewed domain")


def metadata_proof(source,root):
    ensure_authority(source,root)
    gis=source["gis_layer_url"]
    parent=gis.rsplit("/",1)[0]
    # The agency's own homepage independently identifies its GIS operation.
    read_official_government_page(root["official_government_page"],"admin.elpasoco.com")
    service=get_official_json(parent+"?f=json")
    layer=get_official_json(gis+"?f=json")
    if not isinstance(service,dict) or not isinstance(layer,dict) or service.get("error") or layer.get("error"):
        raise ValueError("Government GIS did not return public official metadata")
    service_text=" ".join([
        str(service.get("mapName") or ""),
        str((service.get("documentInfo") or {}).get("Keywords") or ""),
        str((service.get("documentInfo") or {}).get("Title") or ""),
    ]).lower()
    if "flock" not in service_text or ("camera" not in service_text and "cctv" not in service_text):
        raise ValueError("Government Sheriff service does not explicitly identify Flock cameras")
    if layer.get("name")!=root["expected_layer_name"] or layer.get("type")!="Feature Layer" or layer.get("geometryType")!="esriGeometryPoint":
        raise ValueError("County camera layer name or point geometry changed")
    fields=layer.get("fields")
    if not isinstance(fields,list) or len(fields)>100 or not any(
        isinstance(f,dict) and f.get("name")=="OBJECTID" and f.get("type")=="esriFieldTypeOID"
        for f in fields):
        raise ValueError("Government camera layer object ID schema changed")
    if not any(isinstance(f,dict) and f.get("name")=="NAME" for f in fields):
        raise ValueError("Government camera layer location name field missing")
    query=urllib.parse.urlencode({
        "where":"1=1","outFields":"OBJECTID,NAME",
        "outSR":"4326","returnGeometry":"true","f":"json",
        "resultRecordCount":str(MAX_FEATURES)})
    items=get_official_json(gis+"/query?"+query)
    features=items.get("features") if isinstance(items,dict) else None
    if (items.get("error") or not isinstance(features,list) or not 1<=len(features)<MAX_FEATURES
        or items.get("exceededTransferLimit")):
        raise ValueError("Government Flock camera inventory missing or incomplete")
    for entry in features:
        att=entry.get("attributes") if isinstance(entry,dict) else None
        geom=entry.get("geometry") if isinstance(entry,dict) else None
        if not isinstance(att,dict) or type(att.get("OBJECTID")) is not int or not isinstance(geom,dict):
            raise ValueError("County GIS returned malformed camera")
        if (type(geom.get("x")) not in (int,float) or
            type(geom.get("y")) not in (int,float) or not
            (root["bounds_south"]<=geom["y"]<=root["bounds_north"]) or not
            (root["bounds_west"]<=geom["x"]<=root["bounds_east"])):
            raise ValueError("County GIS camera outside approved location scope")
    canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    layer_digest=canonical({"name":layer["name"],"geometryType":layer["geometryType"],
                            "idField":"OBJECTID","fields":[f.get("name") for f in fields if isinstance(f,dict)]})
    service_digest=canonical({"mapName":service.get("mapName"),"documentInfo":service.get("documentInfo") or {}})
    return {"p_source_key":source["source_key"],
            "p_layer_sha":layer_digest,"p_service_sha":service_digest},len(features)


def run(dry_run=False):
    counts=Counter()
    for source,root in get_source_candidates():
        key=source["source_key"]
        try:
            proof,n=metadata_proof(source,root)
            counts["verified_live"]+=1
            print("Owner-bound government layer verified:",key,"features",n)
            if not dry_run:
                ok=api_request("rpc/promote_owner_bound_gis_source",method="POST",payload=proof)
                if ok is not True:
                    raise ValueError("Government promotion refused by database authority checks")
                counts["promoted"]+=1
        except Exception as error:
            counts["held"]+=1
            print("Government GIS source held:",key,type(error).__name__,str(error)[:170])
    for k in ("verified_live","promoted","held"):
        print("Government GIS source",k+":",counts[k])
    return counts


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run",action="store_true")
    run(ap.parse_args().dry_run)
