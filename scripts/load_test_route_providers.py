"""Bounded, fixed-fixture load acceptance for dedicated Photon/OSRM endpoints.

This intentionally REFUSES public demos: no user routes, no paid-provider
testing until the operator explicitly sets approved production endpoint URLs.
"""
import argparse
import concurrent.futures
import math
import statistics
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter

PUBLIC_DEMOS={"photon.komoot.io","router.project-osrm.org"}
SAMPLE_ROUTES=(
    ((-121.4944,38.5816),(-121.1761,38.6779)),  # Sacramento
    ((-73.9854,40.758),(-73.9442,40.73)),       # NYC
    ((-87.6298,41.8781),(-87.6848,41.9214)),  # Chicago
    ((-95.3698,29.7604),(-95.3023,29.735)),   # Houston
    ((-122.3321,47.6062),(-122.2048,47.6101)),# Seattle
    ((-84.3880,33.749),(-84.315,33.752)),     # Atlanta
    ((-112.074,33.448),(-112.051,33.481)),   # Phoenix
    ((-71.0589,42.3601),(-71.093,42.367)),   # Boston
)
SAMPLE_SEARCHES=(
    "Sacramento California","New York New York","Chicago Illinois",
    "Houston Texas","Seattle Washington","Atlanta Georgia",
    "Phoenix Arizona","Boston Massachusetts",
)
MAX_REQUESTS=64

def validate_base(value,allow_local=False):
    parsed=urllib.parse.urlsplit(value)
    hostname=(parsed.hostname or "").lower()
    if(parsed.scheme!="https" or not hostname or parsed.username or
       parsed.password or parsed.port or parsed.query or parsed.fragment):
        raise ValueError("Expected public HTTPS provider base, no credentials or parameters")
    if hostname in PUBLIC_DEMOS:
        raise ValueError("Cannot load-test the public shared OSRM/Photon demos")
    if (hostname in {"localhost","127.0.0.1","::1"} or
         hostname.endswith((".local",".internal"))) and not allow_local:
        raise ValueError("Private hosts cannot be remote load-test targets")
    return value.rstrip("/")

def routing_path(pair):
    a,b=pair
    loc=f"{a[0]},{a[1]};{b[0]},{b[1]}"
    return "/route/v1/driving/"+loc+"?overview=full&geometries=geojson&steps=false&alternatives=true"

def geocode_path(place):
    return "/api/?limit=5&lang=en&q="+urllib.parse.quote(place)

def fetch_json(url,timeout=12):
    req=urllib.request.Request(url,headers={"Accept":"application/json",
      "User-Agent":"Katoptron-route-load-acceptance/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        if response.status!=200:raise ValueError("HTTP "+str(response.status))
        if "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("Invalid content type")
        blob=response.read(6_000_001)
        if len(blob)>6_000_000:raise ValueError("Payload exceeded safe maximum")
        import json
        return json.loads(blob)

def validate(kind,response):
    if kind=="routing":
        return isinstance(response,dict) and response.get("code")=="Ok" and any(
            isinstance(r,dict) and r.get("distance",0)>0 and
            isinstance(r.get("geometry"),dict) and
            r["geometry"].get("type")=="LineString" and
            len(r["geometry"].get("coordinates",[]))>=2
            for r in response.get("routes",[]))
    return (isinstance(response,dict) and isinstance(response.get("features"),list)
        and any(isinstance(f,dict) and f.get("properties",{}).get(
          "countrycode","").upper()=="US" and
          len(f.get("geometry",{}).get("coordinates",[]))>=2
          for f in response["features"]))

def run_test(routing_base,geocoding_base,rounds=2,workers=2,fetch=fetch_json):
    if not isinstance(rounds,int) or not 1<=rounds<=4:
        raise ValueError("Accepts 1-4 fixture rounds only")
    if not isinstance(workers,int) or not 1<=workers<=4:
        raise ValueError("Max concurrency 4, to bound provider traffic")
    routes=validate_base(routing_base)
    geo=validate_base(geocoding_base)
    tasks=[]
    for i in range(rounds):
        for j, pair in enumerate(SAMPLE_ROUTES):
            tasks.append(("routing",routes+routing_path(pair),i,j))
            tasks.append(("geocoding",geo+geocode_path(SAMPLE_SEARCHES[j]),i,j))
    if len(tasks)>MAX_REQUESTS:raise ValueError("Unbounded test fixture size")
    def job(entry):
        kind,url,_,_=entry
        started=time.monotonic()
        try:
            data=fetch(url)
            if not validate(kind,data):raise ValueError("Unexpected provider API schema")
            return (kind,True,round((time.monotonic()-started)*1000),None)
        except Exception as exc:
            return (kind,False,round((time.monotonic()-started)*1000),
                    type(exc).__name__)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(job,tasks):
            results.append(result)
    summary={}
    for kind in ("routing","geocoding"):
        samples=[r for r in results if r[0]==kind]
        latency=sorted(x[2] for x in samples)
        def percentile(p):
            return latency[math.ceil((len(latency)-1)*p)] if latency else None
        summary[kind]={"requests":len(samples),
           "passed":sum(x[1] for x in samples),
           "failed":sum(not x[1] for x in samples),
           "p50_ms":percentile(.5),"p95_ms":percentile(.95),
           "max_ms":max(latency) if latency else None,
           "errors":dict(Counter(x[3] for x in samples if x[3]))}
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing-base",required=True)
    parser.add_argument("--geocoding-base",required=True)
    parser.add_argument("--rounds",type=int,default=2)
    parser.add_argument("--workers",type=int,default=2)
    args=parser.parse_args()
    result=run_test(args.routing_base,args.geocoding_base,args.rounds,args.workers)
    for kind,item in result.items():
        print(kind,":",item)
    if any(r["failed"] or r["p95_ms"]>3000 for r in result.values()):
        raise SystemExit("FAIL: provider did not meet sample reliability gate")
    print("PASS: limited compatibility/load sample; NOT an uptime or capacity SLA")

if __name__=="__main__":main()
