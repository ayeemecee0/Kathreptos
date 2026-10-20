"""Discover and auto-publish only strongly matched official municipal .gov ALPR pages.

Fail closed on ambiguous jurisdiction, redirects, missing evidence, or third-party domains.
The record only asserts that the municipal website publishes Flock ALPR information.
"""
import re
import urllib.parse
import urllib.request
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
 'site:.gov "Flock Safety" "license plate" "City of"',
 'site:.gov "Flock Safety" "ALPR" "City of"',
 'site:.gov "Flock Safety" "police" "City of"',
]
def candidates():
    links=set()
    for q in QUERIES:
        url="https://www.bing.com/search?format=rss&q="+urllib.parse.quote(q)
        try:
            feed=feedparser.parse(url)
            for item in feed.entries:
                link=item.get("link","")
                parsed=urllib.parse.urlsplit(link)
                host=(parsed.hostname or "").lower()
                if parsed.scheme=="https" and host.endswith(".gov") and not parsed.username:
                    links.add(link.split("#")[0])
        except Exception as exc:
            print("Search unavailable:",type(exc).__name__)
    return sorted(links)[:60]

def identify(url,text):
    host=(urllib.parse.urlsplit(url).hostname or "").lower()
    if not host.endswith(".gov"): return None
    # Must explicitly identify the city's government and its state, not just mention a city.
    # City name must also be represented in the government hostname.
    header=text[:1600]
    matches=re.findall(r"\bCity of ([A-Z][A-Za-z]+(?:[ -][A-Z][A-Za-z]+){0,2})\b",header)
    if not matches: return None
    found_states=[(name,code) for name,code in STATES.items() if re.search(r"\b"+re.escape(name)+r"\b",header,re.I)]
    if len(found_states)!=1: return None
    city=matches[0].strip()
    token=re.sub(r"[^a-z]","",city.lower())
    hostparts=re.sub(r"[^a-z]","",host.split(".gov")[0])
    if len(token)<4 or token not in hostparts: return None
    if not re.search(r"\bFlock\s+Safety\b",text,re.I): return None
    if not re.search(r"\b(ALPR|automated license plate reader|automatic license plate reader)s?\b",text,re.I): return None
    return dict(state=found_states[0][1],city=city,agency="City of "+city,
                url=url,publisher="City of "+city,marker=city,
                description="The official City of "+city+" website publishes information about Flock Safety automated license plate readers.")

def main():
    import os
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    base=os.environ["SUPABASE_URL"]
    links=candidates()
    print("Official .gov candidates:",len(links))
    published=0
    for link in links:
        try:
            text=fetch_text(link)
            row=identify(link,text)
            if row:
                publish(row,key,base)
                published+=1
            else: print("Review required (insufficient identity/evidence):",link)
        except Exception as exc:
            print("Review required:",link,type(exc).__name__,str(exc)[:100])
    print("Eligible official pages processed:",published)

if __name__=="__main__":
    main()
