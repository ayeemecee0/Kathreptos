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
              'Lawrenceville, GA':45,'Webster, TX':53,'Newport Beach, CA':69}
MAX_BODY=500_000
MAX_STALE_HOURS=72
MIN_DOCUMENTED_GOV_PROGRAMS=20


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
    if not isinstance(records,list) or len(records)>=5000:
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


def fetch_public_camera_evidence(key):
    rows=[]
    page_size,max_records=80,5000
    for offset in range(0,max_records,page_size):
        query=urllib.parse.urlencode({
            'select':'record_key,jurisdiction_label,verification_status,location_accuracy,source_url,last_source_recheck_at',
            'verification_status':'eq.verified','order':'record_key.asc',
            'limit':page_size,'offset':offset
        })
        page=json.loads(get(PUBLIC_API+'?'+query,{'apikey':key}))
        if not isinstance(page,list) or len(page)>page_size:
            raise ValueError('Public camera API returned an invalid or truncated page')
        rows.extend(page)
        if len(page)<page_size:
            return rows
    raise ValueError('Verified camera evidence exceeds public health scan capacity')


def fetch_public_coverage_areas(key):
    """Page the exact public-only, RLS-filtered original government polygons."""
    rows=[]
    endpoint=PUBLIC_API.replace('/flock_camera_locations','/flock_documented_coverage_areas')
    limit,max_items=40,2000
    for offset in range(0,max_items,limit):
        query=urllib.parse.urlencode({
            'select':'area_key,government_source_key,government_program_key,'
                     'jurisdiction_label,geometry_status,evidence_url,outline_lonlat',
            'geometry_status':'eq.verified','order':'area_key.asc',
            'limit':limit,'offset':offset
        })
        page=json.loads(get(endpoint+'?'+query,{'apikey':key}))
        if not isinstance(page,list) or len(page)>limit:
            raise ValueError('Government polygon public data API malformed or truncated')
        rows.extend(page)
        if len(page)<limit:
            return rows
    raise ValueError('Government polygon inventory exceeds health scan capacity')


def assess_public_area_provenance(rows,expected):
    """Source-specific geometries only. No invented city buffers or circles."""
    if not isinstance(rows,list) or type(expected) is not int or expected<0:
        raise ValueError('Official polygon check inputs malformed')
    ids=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('geometry_status')!='verified':
            raise ValueError('Unverified original government polygon leaked to public map')
        key=row.get('area_key')
        if not isinstance(key,str) or key in ids:
            raise ValueError('Government polygon identity duplicated or missing')
        ids.add(key)
        proof=[row.get('government_source_key'),row.get('government_program_key')]
        if sum(isinstance(p,str) and bool(p) for p in proof)!=1:
            raise ValueError('Polygon missing its single original government authority')
        if (not isinstance(row.get('evidence_url'),str) or
            not row['evidence_url'].startswith('https://')):
            raise ValueError('Government polygon original evidence link missing')
        outline=row.get('outline_lonlat')
        if (not isinstance(outline,list) or not 4<=len(outline)<=250 or
            outline[0]!=outline[-1] or
            not all(isinstance(x,list) and len(x)==2 and
                 all(type(n) in (int,float) for n in x) for x in outline)):
            raise ValueError('Official polygon source geometry invalid')
    if len(rows)!=expected:
        raise ValueError('Public polygon evidence count differs from national map summary')
    return len(rows)


def assess_published_summary(summary,counts):
    if not isinstance(summary,list) or len(summary)!=1:
        raise ValueError('Public national evidence summary unavailable')
    info=summary[0]
    if (info.get('verified_camera_points')!=sum(counts.values()) or
        info.get('verified_point_jurisdictions')!=len(counts)):
        raise ValueError('National evidence summary differs from public camera source inventory')
    if not all(type(info.get(k)) is int and info[k]>=0 for k in (
        'verified_area_polygons','approximate_location_records',
        'documented_government_programs')):
        raise ValueError('Public national evidence metrics invalid')
    if info['documented_government_programs']<MIN_DOCUMENTED_GOV_PROGRAMS:
        raise ValueError('Original government program evidence below reviewed baseline')
    return info


def assess_state_evidence_index(rows,counts,program_total):
    """Ensure browser-facing state footprint is RLS-consistent and complete.

    Unmapped government program disclosures must not count as camera pins.
    Government GIS source labels lacking a confirmed state suffix are omitted
    from state totals, not assigned an invented state.
    """
    if not isinstance(rows,list) or len(rows)>=65 or not rows:
        raise ValueError("Public state evidence footprint missing or truncated")
    expected={}
    for jurisdiction,count in counts.items():
        match=re.search(r", ([A-Z]{2})$",jurisdiction)
        if match:
            expected[match.group(1)]=expected.get(match.group(1),0)+count
    actual={};documented=0
    for row in rows:
        if not isinstance(row,dict) or not re.fullmatch(r"[A-Z]{2}",
                                                      str(row.get("state_code") or "")):
            raise ValueError("Public state evidence label invalid")
        state=row["state_code"]
        if state in actual:
            raise ValueError("Duplicate state evidence row")
        fields=("verified_camera_points","verified_camera_jurisdictions",
                "dated_program_records","terminated_program_records")
        if not all(type(row.get(field)) is int and row[field]>=0 for field in fields):
            raise ValueError("Public state evidence count malformed")
        if (row["terminated_program_records"]>row["dated_program_records"]
            or (row["verified_camera_points"]==0 and row["dated_program_records"]==0)):
            raise ValueError("Public state disclosure without evidence")
        actual[state]=row["verified_camera_points"]
        documented+=row["dated_program_records"]
    if {k:v for k,v in actual.items() if v}!=expected:
        raise ValueError("State GIS camera totals differ from original-source inventory")
    if documented!=program_total:
        raise ValueError("State program disclosures differ from original-government directory")
    return len(rows)


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
    rows=fetch_public_camera_evidence(key)
    counts,last=assess(rows)
    summary_url=PUBLIC_API.replace('/flock_camera_locations','/flock_public_coverage_stats')
    summary=json.loads(get(summary_url+'?select=*',{'apikey':key}))
    totals=assess_published_summary(summary,counts)
    footprint_url=PUBLIC_API.replace('/flock_camera_locations',
                                    '/flock_public_state_evidence_index')
    footprint=json.loads(get(footprint_url+'?select=state_code,verified_camera_points,'
        'verified_camera_jurisdictions,dated_program_records,terminated_program_records'
        '&limit=65',{'apikey':key}))
    states=assess_state_evidence_index(footprint,counts,
       totals['documented_government_programs'])
    areas=fetch_public_coverage_areas(key)
    visible_areas=assess_public_area_provenance(
        areas,totals['verified_area_polygons'])
    print('Verified nationwide published camera points:',totals['verified_camera_points'])
    print('Verified deployment polygons:',visible_areas)
    print('States with independently documented government evidence:',states)
    for j in sorted(counts):
        print('HEALTHY',j,counts[j],'last source verification',last[j].isoformat())
    print('PUBLIC HEALTH PASS: website, disclosures, source data, active GIS freshness and baseline coverage')
    return counts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',default=SITE)
    args=parser.parse_args()
    run(args.site)
