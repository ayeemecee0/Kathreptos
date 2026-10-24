"""Check configured Photon and OSRM compatibility using fixed PUBLIC sample places.
Never use private routes, log address query strings, or claim an SLA from a ping.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=2_000_000
BASE_RE=re.compile(r"^\s*(geocodingServiceBase|routingServiceBase):\s*'([^']+)'\s*,?\s*$",re.M)
DEMO={"geocodingServiceBase":"https://photon.komoot.io",
      "routingServiceBase":"https://router.project-osrm.org"}

def read_settings(text):
    found=dict(BASE_RE.findall(text))
    if set(found)!=set(DEMO):
        raise ValueError("Missing routing/geocoding configuration")
    for key,url in found.items():
        parsed=urllib.request.urlparse(url)
        if (parsed.scheme!="https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.port):
            raise ValueError("Provider URLs must be HTTPS with no public credentials")
    return found

def get_json(url):
    request=urllib.request.Request(url,headers={
        "Accept":"application/json","User-Agent":"Katoptron-public-provider-health/1.0"})
    # No personal data, browser identifiers, route logs or user location.
    with urllib.request.urlopen(request,timeout=13) as response:
        if response.status!=200:raise ValueError("Non-200 provider response")
        if "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("Provider response not JSON")
        payload=response.read(MAX_BYTES+1)
        if len(payload)>MAX_BYTES:raise ValueError("Provider response too large")
        return json.loads(payload)

def validate_geocode(data):
    return (isinstance(data,dict) and isinstance(data.get("features"),list)
       and any(f.get("properties",{}).get("countrycode","").upper()=="US"
        and isinstance(f.get("geometry",{}).get("coordinates"),list)
        and len(f["geometry"]["coordinates"])>=2
        for f in data["features"] if isinstance(f,dict)))

def validate_routing(data):
    if not isinstance(data,dict) or data.get("code")!="Ok":return False
    routes=data.get("routes")
    return isinstance(routes,list) and any(
        isinstance(x,dict) and x.get("distance",0)>500
        and x.get("duration",0)>0 and x.get("geometry",{}).get("type")=="LineString"
        and isinstance(x["geometry"].get("coordinates"),list)
        and len(x["geometry"]["coordinates"])>=2 for x in routes)

def check_all(settings,fetch=get_json):
    from urllib.parse import quote
    # PUBLIC, invariant locations for API schema validation. No user routes.
    sample=quote("Sacramento, California")
    results={}
    queries={
      "geocoding":settings["geocodingServiceBase"].rstrip("/")+"/api/?limit=5&lang=en&q="+sample,
      "routing":settings["routingServiceBase"].rstrip("/")+
         "/route/v1/driving/-121.4944,38.5816;-121.1761,38.6779?overview=full&geometries=geojson&steps=false&alternatives=true"
    }
    for kind,url in queries.items():
        start=time.monotonic()
        try:
            response=fetch(url)
            valid=validate_routing(response) if kind=="routing" else validate_geocode(response)
            if not valid:raise ValueError("Provider output schema is invalid")
            results[kind]={"ok":True,"latency_ms":round((time.monotonic()-start)*1000)}
        except Exception as error:
            # Error class only: don't leak request URL, query or credentials.
            results[kind]={"ok":False,"error_type":type(error).__name__}
    return results

def main():
    settings=read_settings((ROOT/"config.js").read_text(encoding="utf-8"))
    for name,key in (("routing","routingServiceBase"),("geocoding","geocodingServiceBase")):
        service_type="SHARED DEMO (NO SLA)" if settings[key]==DEMO[key] else "CONFIGURED HOST (SLA NOT VERIFIED)"
        print("Provider configuration:",name,service_type)
    report=check_all(settings)
    for name,item in report.items():
        print("Provider public sample health:",name,"PASS" if item["ok"] else "FAIL",
             item.get("latency_ms","—"),item.get("error_type",""))
    if not all(row["ok"] for row in report.values()):
        raise SystemExit("Provider health failed; no claims about camera absence or API availability")
    print("Sample API compatibility confirmed. Service uptime or contractual SLA NOT established.")

if __name__=="__main__":main()
