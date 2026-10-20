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

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Katoptron/1.0 public records research","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=10) as res:
        raw=res.read(1500001)
    if len(raw)>1500000: raise ValueError("API response too large")
    return json.loads(raw)

def enrich(client,mid):
    base="https://webapi.legistar.com/v1/"+client+"/matters/"+str(mid)
    notes=[]
    try:
        histories=get_json(base+"/histories")
        if isinstance(histories,list):
            for h in histories[:5]:
                name=str(h.get("MatterHistoryActionName") or "")
                date=str(h.get("MatterHistoryActionDate") or "")[:10]
                body=str(h.get("MatterHistoryActionBodyName") or "")
                if name: notes.append("Action: "+name[:65]+" ("+date+", "+body[:45]+")")
    except Exception as exc:
        notes.append("Action history unavailable: "+type(exc).__name__)
    try:
        attachments=get_json(base+"/attachments")
        if isinstance(attachments,list):
            names=[str(a.get("MatterAttachmentName") or "")[:65] for a in attachments[:4]]
            notes.append("Attachments listed: "+("; ".join(names) if names else "none"))
    except Exception as exc:
        notes.append("Attachments unavailable: "+type(exc).__name__)
    return " | ".join(notes)

def discover_clients():
    # Identify additional Legistar tenant codes from discovered public links.
    # Tenant identity is not assumed: unknown clients remain labeled by code.
    found={}
    try:
        with open("candidates.json",encoding="utf-8") as file: rows=json.load(file)
        for row in rows:
            for field in ("url","headline","snippet"):
                value=str(row.get(field) or "")
                for match in re.finditer(r"https?://([a-z0-9-]{3,40})\\.legistar\\.com/",value,re.I):
                    code=match.group(1).lower()
                    if code not in CLIENTS: found[code]="Legistar tenant "+code+" (jurisdiction unverified)"
    except (OSError,ValueError,TypeError): pass
    return dict(list(sorted(found.items()))[:12])

def scan(client):
    # Bounded scan; a missed older item is not evidence that it does not exist.
    url="https://webapi.legistar.com/v1/"+client+"/matters?%24top=250&%24orderby=MatterId%20desc"
    rows=get_json(url)
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
        detail=enrich(client,mid)
        leads.append({"url":link,"headline":(title or "Government ALPR agenda matter")[:300],
          "publisher":ACTIVE_CLIENTS[client],"snippet":("Official public agenda matter; manual source verification required. "+body+" | "+detail)[:500],
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
    global ACTIVE_CLIENTS
    ACTIVE_CLIENTS={**CLIENTS,**discover_clients()}
    print("Legistar tenants scanned:",len(ACTIVE_CLIENTS),"discovered:",len(ACTIVE_CLIENTS)-len(CLIENTS))
    all_leads=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tasks={pool.submit(scan,c):c for c in ACTIVE_CLIENTS}
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
