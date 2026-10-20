"""Nationwide official-source discovery with conservative auto-publication.

Discovery can use search results and news leads; publication requires a direct,
HTTPS municipal .gov page with unambiguous municipality/state and Flock ALPR text.
"""
import json
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

def collect():
    links=set()
    counts={"raw":0,"search_errors":0,"direct_gov":0,"non_gov":0,"news_leads":0}
    for q in QUERIES:
        endpoints=[
            ("bing-rss","https://www.bing.com/search?format=rss&q="+urllib.parse.quote(q)),
            ("google","https://www.google.com/search?q="+urllib.parse.quote(q)+"&num=30"),
            ("duckduckgo","https://html.duckduckgo.com/html/?q="+urllib.parse.quote(q)),
            ("google-news","https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=en-US&gl=US&ceid=US:en"),
        ]
        for provider,url in endpoints:
            try:
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=12) as resp:
                    body=resp.read(400000).decode("utf-8","replace")
                if provider in ("bing-rss","google-news"):
                    raw=[e.get("link","") for e in feedparser.parse(body).entries]
                else:
                    parser=Links()
                    parser.feed(body)
                    raw=parser.links
                counts["raw"]+=len(raw)
                for value in raw:
                    link=normalize_url(value)
                    if not link: continue
                    if is_gov(link):
                        links.add(link)
                    else:
                        counts["non_gov"]+=1
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

def main():
    import os
    links=collect()
    print("Official .gov candidates:",len(links))
    verified=0
    held=0
    for link in links:
        try:
            text=fetch_text(link)
            row=identify(link,text)
            if not row:
                held+=1
                print("Held: identity or evidence insufficient:",link)
                continue
            publish(row,os.environ["SUPABASE_SERVICE_ROLE_KEY"],os.environ["SUPABASE_URL"])
            verified+=1
        except Exception as exc:
            held+=1
            print("Held: fetch or publication error:",link,type(exc).__name__,str(exc)[:120])
    print("Eligible official pages processed:",verified)
    print("Official pages held:",held)

if __name__=="__main__":
    main()
