"""Nationwide official-source discovery with conservative auto-publication.

Discovery can use search results and news leads; publication requires a direct,
HTTPS municipal .gov page with unambiguous municipality/state and Flock ALPR text.
"""
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
import feedparser
from auto_publish_official import fetch_text, publish

STATES = {
"Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
"Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
"Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
"Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
"Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO",
"Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ",
"New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND",
"Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI",
"South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT",
"Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV",
"Wisconsin":"WI","Wyoming":"WY"
}
QUERIES = [
 '"Flock Safety" "license plate" site:gov',
 '"Flock Safety" ALPR city police',
 '"Flock Safety" council agenda contract',
 '"Flock Safety" surveillance transparency police',
]

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            link=dict(attrs).get("href")
            if link: self.links.append(link)

def normalize_url(raw):
    try:
        p=urllib.parse.urlsplit(raw)
        if p.hostname in ("html.duckduckgo.com","duckduckgo.com") and p.path.startswith("/l/"):
            raw=urllib.parse.parse_qs(p.query).get("uddg",[""])[0]
            p=urllib.parse.urlsplit(raw)
        if p.hostname in ("google.com","www.google.com") and p.path=="/url":
            raw=urllib.parse.parse_qs(p.query).get("q",[""])[0]
            p=urllib.parse.urlsplit(raw)
        if p.scheme!="https" or not p.hostname or p.username or p.password: return None
        if p.port not in (None,443): return None
        if p.hostname.lower() in ("localhost",): return None
        return urllib.parse.urlunsplit(("https",p.netloc,p.path,p.query,""))
    except ValueError:
        return None

def is_gov(url):
    p=urllib.parse.urlsplit(url)
    host=(p.hostname or "").lower().rstrip(".")
    return host.endswith(".gov") and host!="gov"

def search_provider(item):
    provider,url=item
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=7) as resp:
        body=resp.read(400000).decode("utf-8","replace")
    if provider in ("bing-rss","google-news"):
        return provider,[e.get("link","") for e in feedparser.parse(body).entries]
    parser=Links()
    parser.feed(body)
    return provider,parser.links

def harvest_article(article):
    req=urllib.request.Request(article,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=5) as res:
        if "text/html" not in res.headers.get("Content-Type",""): return []
        if urllib.parse.urlsplit(res.url).hostname != urllib.parse.urlsplit(article).hostname: return []
        body=res.read(250001)
        if len(body)>250000: return []
    parser=Links()
    parser.feed(body.decode("utf-8","replace"))
    return [link for href in parser.links if (link:=normalize_url(urllib.parse.urljoin(article,href))) and is_gov(link)]

def collect():
    links=set()
    article_urls=set()
    counts={"raw":0,"search_errors":0,"direct_gov":0,"non_gov":0,"news_leads":0,"articles_checked":0,"government_links_from_articles":0}
    # Rotate through all 50 states over ten daily runs.
    state_names=list(STATES)
    rotation=datetime.datetime.now(datetime.timezone.utc).timetuple().tm_yday % 10
    state_queries=['"Flock Safety" "license plate" "'+name+'"' for name in state_names[rotation::10]]
    queries=QUERIES[:2]+state_queries
    tasks=[]
    for q in queries:
        tasks.extend([
            ("bing-rss","https://www.bing.com/search?format=rss&q="+urllib.parse.quote(q)),
            ("google-news","https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=en-US&gl=US&ceid=US:en"),
        ])
    print("State search rotation:",rotation,"states:",[name for name in state_names[rotation::10]])
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(search_provider,item):item[0] for item in tasks}
        for future in as_completed(futures):
            provider=futures[future]
            try:
                _,raw=future.result()
                counts["raw"]+=len(raw)
                for value in raw:
                    link=normalize_url(value)
                    if not link: continue
                    if is_gov(link):
                        links.add(link)
                    else:
                        counts["non_gov"]+=1
                        if provider=="bing-rss" and len(article_urls)<36: article_urls.add(link)
                print("Provider",provider,"results",len(raw))
            except Exception as exc:
                counts["search_errors"]+=1
                print("Provider error",provider,type(exc).__name__,str(exc)[:100])
    # Google News links are often redirectors. Preserve them as leads, never as
    # publication evidence; only directly resolvable official URLs are eligible.
    path=Path("candidates.json")
    if path.exists():
        for row in json.loads(path.read_text(encoding="utf-8")):
            counts["news_leads"]+=1
            link=normalize_url(row.get("url",""))
            if link and is_gov(link): links.add(link)
            elif link and not urllib.parse.urlsplit(link).hostname.endswith("google.com") and len(article_urls)<24:
                article_urls.add(link)
    # Follow a small bounded sample of public articles and harvest only direct
    # outbound .gov citations. News claims themselves never qualify as evidence.
    # Reject redirects and oversized/non-HTML responses; only .gov destinations
    # are ever passed to the publication stage.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(harvest_article,article):article for article in sorted(article_urls)[:30]}
        for future in as_completed(futures):
            try:
                found=future.result()
                counts["articles_checked"]+=1
                for link in found:
                    if link not in links: counts["government_links_from_articles"]+=1
                    links.add(link)
            except Exception as exc:
                print("Article citation harvest skipped:",type(exc).__name__)
    counts["direct_gov"]=len(links)
    print("Discovery diagnostics:",json.dumps(counts,sort_keys=True))
    return sorted(links)[:60]

def identify(url,text):
    if not is_gov(url): return None
    # We require municipal identity in both the page and the domain; a general
    # article about another city's program does not qualify.
    header=text[:3500]
    city_matches=re.findall(r"\bCity of ([A-Z][A-Za-z]+(?:[ -][A-Z][A-Za-z]+){0,2})\b",header)
    states=[(name,code) for name,code in STATES.items() if re.search(r"\b"+re.escape(name)+r"\b",header,re.I)]
    if len(city_matches)!=1 or len(states)!=1: return None
    city=city_matches[0].strip()
    domain=re.sub("[^a-z]","",urllib.parse.urlsplit(url).hostname.lower())
    city_token=re.sub("[^a-z]","",city.lower())
    if len(city_token)<4 or city_token not in domain: return None
    if not re.search(r"\bFlock\s+Safety\b",text,re.I): return None
    if not re.search(r"\b(?:ALPR|automated license plate readers?|automatic license plate readers?)\b",text,re.I): return None
    return dict(state=states[0][1],city=city,agency="City of "+city,
                url=url,publisher="City of "+city,marker=city,
                description="The official City of "+city+" website publishes information about Flock Safety automated license plate readers.")

def queue_for_review(link, reason, key, base):
    payload=[{"url":link,"headline":"Official government ALPR source — verification required",
              "publisher":urllib.parse.urlsplit(link).hostname,
              "snippet":reason[:500],"status":"unreviewed"}]
    endpoint_query="?on_conflict=url"
    import json as _json
    data=_json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(base.rstrip("/")+"/rest/v1/discovery_queue"+endpoint_query,
        data=data,method="POST",headers={"apikey":key,"Authorization":"Bearer "+key,
        "Content-Type":"application/json","Prefer":"resolution=ignore-duplicates,return=minimal"})
    with urllib.request.urlopen(req,timeout=20) as response:
        return response.status

def main():
    import os
    links=collect()
    print("Official .gov candidates:",len(links))
    verified=0
    held=0
    queued=0
    for link in links:
        try:
            text=fetch_text(link)
            row=identify(link,text)
            if not row:
                held+=1
                print("Held: identity or evidence insufficient:",link)
                try:
                    queue_for_review(link,"Page fetched, but agency identity or Flock ALPR evidence did not meet publication rules",os.environ["SUPABASE_SERVICE_ROLE_KEY"],os.environ["SUPABASE_URL"])
                    queued+=1
                except Exception as queue_exc: print("Queue error:",type(queue_exc).__name__)
                continue
            publish(row,os.environ["SUPABASE_SERVICE_ROLE_KEY"],os.environ["SUPABASE_URL"])
            verified+=1
        except Exception as exc:
            held+=1
            print("Held: fetch or publication error:",link,type(exc).__name__,str(exc)[:120])
            try:
                queue_for_review(link,"Official-source fetch or publication failed: "+type(exc).__name__+" "+str(exc)[:180],os.environ["SUPABASE_SERVICE_ROLE_KEY"],os.environ["SUPABASE_URL"])
                queued+=1
            except Exception as queue_exc: print("Queue error:",type(queue_exc).__name__)
    print("Eligible official pages processed:",verified)
    print("Official pages held:",held)
    print("Official sources submitted to review queue:",queued)

if __name__=="__main__":
    main()
