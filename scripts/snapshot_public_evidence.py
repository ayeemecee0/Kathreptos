"""Bounded, public-only Katoptron evidence snapshot for release/incident comparison.

THIS IS NOT A PRIVATE DATABASE BACKUP. It copies only information already
available to anonymous readers, using only the site's publishable key.
Never add private community, auth, or reviewer tables to this allowlist.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
API='https://bpvkapswslmgfazbzpsv.supabase.co/rest/v1'
MAX_ROWS_PER_FEED=5000
PAGE_SIZE=200
FEEDS={
 'overview':('flock_analytics_overview','*',''),
 'states':('flock_analytics_states','*',''),
 'monthly_evidence':('flock_analytics_monthly_evidence','*',''),
 'government_accountability':('flock_accountability_directory','*',''),
 'individual_official_positions':('flock_individual_public_positions',
   'position_key,person_name,office_title,jurisdiction_label,state_code,record_kind,recorded_position,action_date,document_reference,evidence_description,original_government_url,source_kind',''),
 'verified_camera_points':('flock_camera_locations',
   'record_key,jurisdiction_label,latitude,longitude,source_url,verification_status,location_accuracy,last_source_recheck_at',
   'verification_status=eq.verified&location_accuracy=eq.exact'),
}
BANNED_WORDS=('flock_community_submissions','flock_community_screening',
  'auth.users','flock_community_review_history','flock_community_evidence')

def public_key(path=ROOT/'config.js'):
    match=re.search(r"supabasePublishableKey:\s*'([^']+)'",path.read_text(encoding='utf8'))
    if not match or not match.group(1).startswith('sb_publishable_'):
        raise ValueError('Public-only publishable key was not found in config.js')
    return match.group(1)

def verify_allowlist():
    for table,select,filters in FEEDS.values():
        if any(term in (table+' '+select+' '+filters).lower() for term in BANNED_WORDS):
            raise ValueError('Private or credential-derived data requested')
        if not re.fullmatch('[a-z][a-z_0-9]+',table):
            raise ValueError('Invalid allowlisted endpoint')
    if len(set(t for t,_,_ in FEEDS.values()))!=len(FEEDS):
        raise ValueError('Duplicate public feeds')

def retrieve(table,select,filters,key):
    result=[]
    for offset in range(0,MAX_ROWS_PER_FEED,PAGE_SIZE):
        params=urllib.parse.urlencode({'select':select,'limit':PAGE_SIZE,'offset':offset})
        url=API+'/'+table+'?'+params+('&'+filters if filters else '')
        request=urllib.request.Request(url,headers={
          'apikey':key,'Accept':'application/json','User-Agent':'Katoptron-public-evidence-snapshot/1.0'
        })
        with urllib.request.urlopen(request,timeout=25) as response:
            if response.geturl()!=url:
                raise ValueError('Unexpected data endpoint redirect')
            if response.headers.get('content-type','').split(';')[0]!='application/json':
                raise ValueError('Public data endpoint was not JSON')
            content=response.read(2_000_001)
        if len(content)>2_000_000:raise ValueError('Public page too large')
        page=json.loads(content)
        if not isinstance(page,list) or len(page)>PAGE_SIZE:
            raise ValueError('Public page malformed or truncated')
        result.extend(page)
        if len(page)<PAGE_SIZE:return result
    raise ValueError('Public source exceeds 5000-row snapshot cap; do not silently truncate')

def validate_payload(data):
    overview=data['overview']
    if len(overview)!=1:raise ValueError('Public evidence overview missing')
    metrics=overview[0]
    if (metrics.get('exact_government_points') != len(data['verified_camera_points'])
     or metrics.get('accountability_records') != len(data['government_accountability'])):
        raise ValueError('Public snapshot violates source reconciliation')
    if metrics.get('states_with_any_documented_evidence')!=len(data['states']):
        raise ValueError('State documentary index disagrees with national count')
    if metrics.get('documented_individual_positions')!=len(data['individual_official_positions']):
        raise ValueError('Published named government positions disagree with overview')
    keys=[str(x.get('event_key')) for x in data['government_accountability']]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate government source events')
    for row in data['government_accountability']:
        if not str(row.get('source_url','')).startswith('https://'):
            raise ValueError('Government event lacks original HTTPS source')
    return True

def capture():
    verify_allowlist()
    key=public_key()
    data={name:retrieve(*spec,key) for name,spec in FEEDS.items()}
    validate_payload(data)
    return data

def create_snapshot(data,when=None):
    validate_payload(data)
    stamp=(when or dt.datetime.now(dt.timezone.utc)).isoformat()
    packed=json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')
    return {'schema_version':1,'scope':'ANONYMOUS_PUBLIC_EVIDENCE_ONLY',
            'captured_at_utc':stamp,'sha256_of_data':hashlib.sha256(packed).hexdigest(),
            'record_counts':{k:len(v) for k,v in data.items()},'data':data}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='.evidence/public-evidence-snapshot.json')
    args=parser.parse_args()
    snapshot=create_snapshot(capture())
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    temp.replace(path)
    print('Verified public evidence snapshot',snapshot['record_counts'])
    print('Public-only SHA256:',snapshot['sha256_of_data'])
if __name__=='__main__':main()
