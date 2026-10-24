"""Read-only live launch gates: private Storage bucket and discovery conversion.

Operates solely against fixed Katoptron Supabase endpoints using the existing
GitHub Actions service credential. Does not retrieve Storage objects, private
submission rows, candidate coordinates, personal data, or any token values.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

PROJECT='https://bpvkapswslmgfazbzpsv.supabase.co'
BUCKET='katoptron-community-evidence'
MAX_METADATA_BYTES=8192
MAX_COUNT=1_000_000
EXPECTED_MIMES={'image/jpeg','image/png','image/webp'}
# Only anonymous-safe aggregate metrics are printed. They are counts of
# research *candidates*, not verified cameras or a production surveillance map.
STAGES=(
 ('verified_exact_camera_points','flock_camera_locations','verification_status=eq.verified&location_accuracy=eq.exact'),
 ('unverified_gis_sources','flock_gis_source_candidates','trust_status=eq.unverified'),
 ('unverified_camera_candidates','flock_camera_discovery_candidates','candidate_status=eq.unverified'),
 ('independently_matched_candidates','flock_camera_source_matches',''),
 ('original_government_gis_pages','government_gis_search_queue',''),
 ('direct_government_gis_receipts','government_gis_disclosure_leads',''),
 ('externally_verified_authorities','official_external_flock_gis_authorities','verification_status=eq.verified'),
 ('first_party_agency_source_receipts','first_party_agency_gis_receipts',''),
)
# Stable primary keys guarantee no SELECT * or latent confidential fields.
IDENTITIES={
 'flock_camera_locations':'record_key',
 'flock_gis_source_candidates':'gis_layer_url',
 'flock_camera_discovery_candidates':'candidate_key',
 'flock_camera_source_matches':'candidate_key',
 'government_gis_search_queue':'page_url',
 'government_gis_disclosure_leads':'disclosure_url',
 'official_external_flock_gis_authorities':'source_key',
 'first_party_agency_gis_receipts':'source_key',
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Unexpected redirect in private launch health check')

def transport(method,url,key):
    """Fetch only bucket metadata or an HTTP HEAD count, never private rows."""
    if url!=PROJECT+'/storage/v1/bucket/'+BUCKET and not url.startswith(PROJECT+'/rest/v1/'):
        raise ValueError('Refusing arbitrary credential-bearing URL')
    if method not in ('GET','HEAD'):
        raise ValueError('Read-only GET and HEAD methods required')
    if method=='GET' and url!=PROJECT+'/storage/v1/bucket/'+BUCKET:
        raise ValueError('Only the fixed private bucket metadata may be downloaded')
    request=urllib.request.Request(url,method=method,headers={
        'apikey':key,'Authorization':'Bearer '+key,
        'Accept':'application/json','User-Agent':'Katoptron-readonly-launch-health/1.0',
        'Prefer':'count=exact' if method=='HEAD' else '',
    })
    with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as response:
        if response.geturl()!=url:
            raise ValueError('Unexpected health check redirect')
        if response.status not in (200,206):
            raise ValueError('Read-only Supabase health response unavailable')
        if method=='HEAD':
            # Reading only a Content-Range header avoids private record data.
            return response.headers.get('Content-Range')
        if not response.headers.get('Content-Type','').lower().startswith('application/json'):
            raise ValueError('Storage metadata did not return JSON')
        raw=response.read(MAX_METADATA_BYTES+1)
        if not raw or len(raw)>MAX_METADATA_BYTES:
            raise ValueError('Unexpected private bucket metadata size')
        return json.loads(raw)

def verify_bucket(data):
    if not isinstance(data,dict):
        raise ValueError('Private evidence Storage bucket metadata missing')
    if data.get('id')!=BUCKET or data.get('public') is not False:
        raise ValueError('CRITICAL: private evidence bucket missing or publicly exposed')
    if type(data.get('file_size_limit')) is not int or data['file_size_limit']>3145728 or data['file_size_limit']<1:
        raise ValueError('Private evidence upload size guard removed')
    mimes=data.get('allowed_mime_types')
    if not isinstance(mimes,list) or not mimes or any(not isinstance(x,str) for x in mimes):
        raise ValueError('Storage allowed MIME types missing')
    if not set(mimes)<=EXPECTED_MIMES:
        raise ValueError('Private evidence bucket permits unexpected file types')
    return True

def extract_count(header):
    if not isinstance(header,str):
        raise ValueError('PostgREST exact count header missing')
    match=re.fullmatch(r'(?:\*|\d+-\d+)/(\d+)',header.strip())
    if not match:
        raise ValueError('PostgREST response did not include a trustworthy total count')
    value=int(match[1])
    if value>MAX_COUNT:
        raise ValueError('Evidence queue exceeds bounded monitor capacity')
    return value

def tally(key,send=transport):
    if not key or not isinstance(key,str) or len(key)>500 or not (
        key.startswith('sb_secret_') or
        # Existing deployments may still use JWT-format service credentials.
        key.startswith('eyJ')
    ):
        raise ValueError('Server-only Supabase service credentials required')
    # Check the privacy-critical bucket first. It must never become public.
    verify_bucket(send('GET',PROJECT+'/storage/v1/bucket/'+BUCKET,key))
    stats={}
    for label,table,filters in STAGES:
        if table not in IDENTITIES:
            raise ValueError('Unreviewed private database endpoint')
        params={'select':IDENTITIES[table],'limit':'1'}
        url=PROJECT+'/rest/v1/'+table+'?'+urllib.parse.urlencode(params)
        if filters:
            url+='&'+filters
        stats[label]=extract_count(send('HEAD',url,key))
    if stats['verified_exact_camera_points']<293:
        # Existing public camera health monitor also checks source-specific
        # baselines; this catches total publication loss before a false zero.
        raise ValueError('Verified exact camera total below reviewed baseline')
    if stats['first_party_agency_source_receipts']<1:
        raise ValueError('Independently authenticated original agency GIS authority missing')
    # Empty direct links are an actionable discovery weakness, but not
    # evidence loss: never auto-promote ambiguous or vendor-controlled maps.
    return stats

def run():
    key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
    stats=tally(key)
    print('PRIVATE STORAGE GUARD PASS: bucket private, max 3 MB, images only')
    for label in sorted(stats):
        print('DISCOVERY AGGREGATE',label,stats[label])
    if (stats['unverified_camera_candidates'] and
        not stats['direct_government_gis_receipts']):
        print('DISCOVERY CONVERSION WARNING: no exact original-government GIS '
              'receipt; do not equate raw candidates with verified locations')
    print('READ-ONLY LAUNCH HEALTH PASS: no private rows, photo bytes or tokens printed')

if __name__=='__main__':
    run()
