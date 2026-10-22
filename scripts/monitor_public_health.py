"""Katoptron public production health monitor (read-only, no service credentials).

Checks: static site/pages, public camera API, verified source inventory and
recent verification. Failed checks produce a nonzero GitHub Actions status,
not a false claim that cameras are absent. Historical count thresholds should
be updated only after a justified source withdrawal and evidence audit.
"""
import argparse
import datetime as dt
import json
import re
import urllib.parse
import urllib.request

SITE='https://ayeemecee0.github.io/Katoptron/'
PUBLIC_API='https://bpvkapswslmgfazbzpsv.supabase.co/rest/v1/flock_camera_locations'
EXPECTED_MIN={'Monroe, WA':18,'El Paso County, CO':16,'Peoria, AZ':74,
              'Lawrenceville, GA':45,'Webster, TX':53}
MAX_BODY=500_000
MAX_STALE_HOURS=72


def get(url,headers=None):
    request=urllib.request.Request(url,headers={
        'Accept':'application/json,text/html,application/javascript',
        'User-Agent':'Katoptron/1.0 public health check',
        **(headers or {}),
    })
    with urllib.request.urlopen(request,timeout=25) as response:
        if response.geturl()!=url:
            raise ValueError('Unexpected redirect in production health check')
        raw=response.read(MAX_BODY+1)
    if len(raw)>MAX_BODY or not raw:
        raise ValueError('Public response too large or empty')
    return raw.decode('utf8','replace')


def public_key(config):
    m=re.search(r"supabasePublishableKey:\s*'([^']+)'",config)
    if not m or not m.group(1).startswith('sb_publishable_'):
        raise ValueError('Unable to locate current PUBLIC Supabase publishable key')
    return m.group(1)


def assess(records,now=None,minimum=EXPECTED_MIN):
    if now is None:now=dt.datetime.now(dt.timezone.utc)
    if not isinstance(records,list) or len(records)>=1200:
        raise ValueError('Public camera list missing or truncated')
    counts={}
    last={}
    for row in records:
        if not isinstance(row,dict):
            raise ValueError('Invalid public camera entry')
        jurisdiction=row.get('jurisdiction_label')
        if not isinstance(jurisdiction,str):
            raise ValueError('Camera missing jurisdiction')
        if row.get('verification_status')!='verified':
            raise ValueError('Revoked/uncertain record leaked into public query')
        if row.get('location_accuracy')!='exact':
            continue  # Approximate deployment areas are not counted as points.
        if not isinstance(row.get('source_url'),str) or not row['source_url'].startswith('https://'):
            raise ValueError('Published evidence link missing')
        checked=row.get('last_source_recheck_at')
        if not checked:
            raise ValueError('Published point has no government source recheck timestamp')
        stamp=dt.datetime.fromisoformat(checked.replace('Z','+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Source recheck lacks timezone')
        if stamp>now+dt.timedelta(minutes=15):
            raise ValueError('Government source timestamp is in the future')
        if now-stamp>dt.timedelta(hours=MAX_STALE_HOURS):
            raise ValueError('Government GIS verification stale for '+jurisdiction)
        counts[jurisdiction]=counts.get(jurisdiction,0)+1
        last[jurisdiction]=max(last.get(jurisdiction,stamp),stamp)
    for jurisdiction,target in minimum.items():
        if counts.get(jurisdiction,0)<target:
            raise ValueError('Verified coverage below baseline for '+jurisdiction+
                             ': '+str(counts.get(jurisdiction,0))+' < '+str(target))
    return counts,last


def run(site=SITE):
    if not site.startswith('https://'):
        raise ValueError('Health checks must use live HTTPS website')
    html=get(site)
    if 'Katoptron' not in html or './map.js' not in html or './route-geometry.js' not in html:
        raise ValueError('Primary camera map is missing its runtime or content')
    for path,anchor in (
      ('map.js','loadRouteEvidence'),
      ('route-geometry.js','closestOnRoute'),
      ('privacy.html','Privacy and data handling'),
      ('methodology.html','Camera evidence methodology'),
    ):
        if anchor not in get(urllib.parse.urljoin(site,path)):
            raise ValueError('Deployed public page or route runtime missing: '+path)
    config=get(urllib.parse.urljoin(site,'config.js'))
    key=public_key(config)
    url=PUBLIC_API+'?'+urllib.parse.urlencode({
       'select':'jurisdiction_label,verification_status,location_accuracy,source_url,last_source_recheck_at',
       'verification_status':'eq.verified','limit':'1200'})
    rows=json.loads(get(url,{'apikey':key}))
    counts,last=assess(rows)
    for j in sorted(counts):
        print('HEALTHY',j,counts[j],'last source verification',last[j].isoformat())
    print('PUBLIC HEALTH PASS: website, disclosures, source data, active GIS freshness and baseline coverage')
    return counts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',default=SITE)
    args=parser.parse_args()
    run(args.site)
