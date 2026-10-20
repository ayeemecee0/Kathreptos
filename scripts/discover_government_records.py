"""Read official public Legistar agenda records and queue ALPR matches for review.

No agenda match is automatically published as a verified action or contract.
"""
import concurrent.futures
import json
import os
import re
import urllib.parse
import urllib.request

# Explicitly identified municipal Legistar tenants. Expand only after confirming identity.
CLIENTS={"costamesa":"Costa Mesa, CA","seattle":"Seattle, WA","oakland":"Oakland, CA","lacounty":"Los Angeles County, CA"}
TERMS=re.compile(r"\b(?:flock\s+safety|automated?\s+license\s+plate\s+readers?|ALPR|LPR\s+cameras?)\b",re.I)

def scan(client):
    # Bounded scan; a missed older item is not evidence that it does not exist.
    url="https://webapi.legistar.com/v1/"+client+"/matters?%24top=250&%24orderby=MatterId%20desc"
    req=urllib.request.Request(url,headers={"User-Agent":"Katoptron/1.0 public records research","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=12) as res:
        raw=res.read(2000001)
    if len(raw)>2000000: raise ValueError("Response too large")
    rows=json.loads(raw)
    if not isinstance(rows,list): raise ValueError("Unexpected API response")
    leads=[]
    for row in rows:
        if not isinstance(row,dict): continue
        title=str(row.get("MatterName") or "")
        body=" ".join(str(row.get(k) or "") for k in ("MatterName","MatterTitle","MatterTypeName"))
        if not TERMS.search(body): continue
        mid=row.get("MatterId")
        if not isinstance(mid,int): continue
        link="https://"+client+".legistar.com/LegislationDetail.aspx?ID="+str(mid)
        leads.append({"url":link,"headline":(title or "Government ALPR agenda matter")[:300],
          "publisher":CLIENTS[client],"snippet":("Official public agenda matter; manual source verification required. "+body)[:500],
          "status":"unreviewed"})
    return leads

def queue(lead):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req=urllib.request.Request(base+"/rest/v1/discovery_queue?on_conflict=url",
      data=json.dumps([lead]).encode("utf-8"),method="POST",
      headers={"apikey":key,"Authorization":"Bearer "+key,"Content-Type":"application/json",
               "Prefer":"resolution=ignore-duplicates,return=minimal"})
    with urllib.request.urlopen(req,timeout=12) as res: return res.status

def main():
    all_leads=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(scan,c):c for c in CLIENTS}
        for task in concurrent.futures.as_completed(tasks):
            client=tasks[task]
            try:
                matches=task.result()
                all_leads.extend(matches)
                print("Official agenda matches:",client,len(matches))
            except Exception as exc:
                print("Official agenda source unavailable:",client,type(exc).__name__,str(exc)[:120])
    unique={x["url"]:x for x in all_leads}
    print("Unique official agenda leads:",len(unique))
    queued=0
    for lead in unique.values():
        try:
            queue(lead)
            queued+=1
        except Exception as exc:
            print("Agenda queue error:",type(exc).__name__,str(exc)[:120])
    print("Official agenda leads queued:",queued)
    print("Agenda records auto-published: 0 (review required)")

if __name__=="__main__": main()
