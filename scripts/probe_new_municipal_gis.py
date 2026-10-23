"""Read-only probes of newly discovered original-city Flock camera GIS layers.
No Supabase credentials, no mutation or public camera publication.
"""
import collections
import urllib.parse
from auto_verify_camera_gis import get_official_json

SOURCES = [
 {"name":"Lawrenceville GA","url":"https://gisinfo.lawrencevillega.org/server/rest/services/MyCityServices/MyCityServices/MapServer/29",
  "bounds":(33.75,-84.15,34.1,-83.85)},
 {"name":"Webster TX","url":"https://www1.cityofwebster.com/arcgis/rest/services/Landbase/Cameras_Licence_Plates1/MapServer/0",
  "bounds":(29.47,-95.2,29.61,-95.05)},
 {"name":"Alachua County FL","url":"https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0",
  "bounds":(29.2,-82.9,30.15,-82.0)},
 {"name":"Newport Beach CA public Geocortex Police Layers GIS","url":"https://nbgis.newportbeachca.gov/arcgis/rest/services/EmployeeMasterMap/MapServer/299",
  "bounds":(33.52,-117.98,33.77,-117.69),"privacy_sensitive":True},
]
def evaluate(s):
    root=s["url"].rsplit("/",1)[0]
    service=get_official_json(root+"?f=json")
    meta=get_official_json(s["url"]+"?f=json")
    if service.get("error") or meta.get("error"):raise ValueError("GIS service metadata error")
    print("GIS SOURCE METADATA",s["name"],
          "source layer",meta.get("name"),
          "geometry",meta.get("geometryType"),
          "objectIdField",meta.get("objectIdField"),
          "fields",[(x.get("name"),x.get("type")) for x in meta.get("fields",[]) if isinstance(x,dict)][:45],
          "service summary",str(service.get("serviceDescription") or service.get("mapName") or "")[:240])
    if meta.get("geometryType")!="esriGeometryPoint" or meta.get("type")!="Feature Layer":
        raise ValueError("Not published point camera features")
    original_fields=[f for f in meta.get("fields",[]) if isinstance(f,dict)]
    fields={f.get("name") for f in original_fields}
    objectid=meta.get("objectIdField")
    if not isinstance(objectid,str) or not objectid:
        candidates=[f.get("name") for f in original_fields
                    if f.get("type")=="esriFieldTypeOID"]
        if len(candidates)==1:objectid=candidates[0]
    if not objectid or objectid not in fields or not any(
        f.get("name")==objectid and f.get("type")=="esriFieldTypeOID"
        for f in original_fields):
        raise ValueError("No independently typed original GIS identity")
    exposed=(objectid+",FlockUnitNo,FlockName" if s.get("privacy_sensitive")
             else "*")
    query=urllib.parse.urlencode({"where":"1=1","outFields":exposed,
              "outSR":4326,"returnGeometry":"true",
              "resultRecordCount":999,"orderByFields":objectid+" ASC","f":"json"})
    data=get_official_json(s["url"]+"/query?"+query)
    features=data.get("features")
    if not isinstance(features,list) or not features or len(features)>=999 or data.get("exceededTransferLimit"):
        raise ValueError("Features empty or truncated")
    types=collections.Counter()
    valid=0
    examples=[]
    ids=set()
    lo,west,hi,east=s["bounds"]
    for f in features:
        attrs=f.get("attributes") or {}
        geom=f.get("geometry") or {}
        oid=attrs.get(objectid)
        if oid in ids or type(oid) is not int:raise ValueError("Duplicate/missing GIS feature IDs")
        ids.add(oid)
        typ=str(attrs.get("CameraType") or attrs.get("Type") or
                ("Original city Flock Unit Locations" if s.get("privacy_sensitive")
                 else "NO_TYPE"))[:65]
        types[typ]+=1
        if (type(geom.get("x")) in (float,int) and type(geom.get("y")) in (float,int)
            and lo<=geom["y"]<=hi and west<=geom["x"]<=east):
            valid+=1
        # Public GeoCortex references a broad EmployeeMasterMap. Inspect
        # aggregate schema/counts without logging individual geometry here
        # until independent disclosure and source-authority review.
        if not s.get("privacy_sensitive") and len(examples)<4:
            examples.append({"id":oid,"camera_id":str(attrs.get("CameraID") or attrs.get("ID") or "")[:28],
                             "type":typ,"lat":round(geom.get("y",0),5),
                             "lon":round(geom.get("x",0),5)})
    print("GIS PROBE",s["name"],"service",s["url"],"layer",meta.get("name"),
          "geometry",meta.get("geometryType"),"total",len(features),"in-area",valid,
          "type_breakdown",dict(types),"fields",sorted(fields),"examples",examples,
          "government_service_description",str(service.get("serviceDescription") or "")[:210])
    return valid

if __name__=="__main__":
    for source in SOURCES:
        try:
            evaluate(source)
        except Exception as err:
            print("GIS PROBE HELD",source["name"],type(err).__name__,str(err)[:190])
