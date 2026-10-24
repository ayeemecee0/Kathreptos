"""Live anonymous-access regression against *private* Katoptron API resources.

Uses the browser-PUBLIC API key only. It never reads response bodies, prints
private records, signs in, edits data, or requests storage objects.
Private report/reviewer endpoints must be denied even when their tables are empty.
"""
from pathlib import Path
import json
import urllib.error
import urllib.parse
import urllib.request

from monitor_public_health import public_key

ROOT=Path(__file__).resolve().parents[1]
BASE='https://bpvkapswslmgfazbzpsv.supabase.co/rest/v1'
PRIVATE_TABLES=(
    'flock_community_submissions',
    'flock_community_review_history',
    'flock_community_screening',
    'flock_point_evidence_cases',
    'flock_point_evidence_attestations',
    'editorial_reviewers',
    'agenda_evidence_reviews',
)
# Probe only non-mutating RPCs, with their full valid argument signatures.
# PostgreSQL marks these VOLATILE, so GET would be rejected by PostgREST even
# if anonymous EXECUTE had accidentally been granted (a dangerous false pass).
# Write RPC grants remain tested by the separate SQL release-invariant gate.
PRIVATE_RPC={
    'editorial_session': {},
    'list_community_review_queue': {'p_limit':1},
    'community_report_attachment_paths': {
        'p_report':'00000000-0000-0000-0000-000000000000',
    },
}
DENIED=(401,403)
MAX_CHECKS=20

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Unexpected redirect from private API')

def status_only(url,key,method='GET',payload=None):
    """Return status without reading or exposing any private payload."""
    if not url.startswith(BASE+'/'):
        raise ValueError('Private endpoint must use the exact production API')
    if method=='POST':
        if not url.startswith(BASE+'/rpc/') or not isinstance(payload,dict):
            raise ValueError('POST is restricted to approved read-only RPC probes')
    elif method!='GET' or payload is not None:
        raise ValueError('Unapproved private boundary probe method')
    headers={
        'apikey':key,
        'Accept':'application/json',
        'User-Agent':'Katoptron-private-public-boundary/1.0',
    }
    if method=='POST':
        headers['Content-Type']='application/json'
    request=urllib.request.Request(url,method=method,headers=headers,
        data=json.dumps(payload).encode('utf8') if method=='POST' else None)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=18) as response:
            return response.status   # Intentionally do not read the body.
    except urllib.error.HTTPError as exc:
        return exc.code

def assert_denied(status,endpoint):
    if status not in DENIED:
        # Never echo a response body or potentially sensitive response.
        raise ValueError('Anonymous private API accessible or not reliably denied: '+endpoint+
                         ' (HTTP '+str(status)+')')

def check_boundaries(key,fetch=status_only):
    if not key.startswith('sb_publishable_'):
        raise ValueError('Only a public publishable key is permitted')
    total=0
    for table in PRIVATE_TABLES:
        # A 200 [] response is *not* acceptable: no anonymous table access
        # should exist even before the first real community submission.
        url=BASE+'/'+table+'?'+urllib.parse.urlencode({'select':'*','limit':1})
        assert_denied(fetch(url,key),table)
        total+=1
    # PostgREST responds with 404 for unexposed functions on some versions;
    # inaccessible functions are safe too. But any successful invocation,
    # even one returning false or an empty queue, is an auth boundary defect.
    for rpc,payload in PRIVATE_RPC.items():
        url=BASE+'/rpc/'+rpc
        status=fetch(url,key,method='POST',payload=payload)
        if status not in (401,403,404):
            raise ValueError('Anonymous sensitive RPC unexpectedly callable: '+rpc+
                             ' (HTTP '+str(status)+')')
        total+=1
    if total>MAX_CHECKS:
        raise ValueError('Private boundary probe budget exceeded')
    return total

def run():
    key=public_key((ROOT/'config.js').read_text(encoding='utf8'))
    count=check_boundaries(key)
    print('PRIVATE BOUNDARY PASS:',count,
          'anonymous database/RPC endpoints denied; no records or secrets retrieved')

if __name__=='__main__':
    run()
