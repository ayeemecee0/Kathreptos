            self.in_title = True
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
    def handle_data(self, data):
        self.words.append(data)

def fetch(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': UA, 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=12) as resp:
        final = urllib.parse.urlsplit(resp.url)
        raw = resp.read(MAX_PAGE + 1)
        ctype = resp.headers.get('Content-Type', '')
    if len(raw) > MAX_PAGE:
        raise ValueError('oversize page')
    return final, ctype, raw

def valid_gov_url(value):
    try:
        p = urllib.parse.urlsplit(value)
        return (p.scheme == 'https' and p.hostname is not None and
                bool(GOV.search(p.hostname)) and not p.username and not p.password and
                p.port in (None, 443))
    except ValueError:
        return False

def tenant_host(value):
    try:
        p = urllib.parse.urlsplit(value)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            return None
        return (p.hostname or '').lower() if TENANT.fullmatch(p.hostname or '') else None
    except ValueError:
        return None

def identity_terms(label):
    # Require a distinctive jurisdiction name plus state abbreviation or full state
    # to occur on the official page. Avoid generic labels and placeholders.
    if not isinstance(label, str) or ',' not in label:
        return None
    place, state = [s.strip() for s in label.rsplit(',', 1)]
    if not re.fullmatch(r'[A-Za-z][A-Za-z .\'-]{3,70}', place):
        return None
    if not re.fullmatch(r'[A-Za-z ]{2,25}', state):
        return None
    if place.lower().startswith('legistar tenant'):
        return None
    return place, state

def verify(row):
    source = str(row.get('source_url') or '')
    evidence = str(row.get('evidence_url') or '')
    label = row.get('jurisdiction_label')
    host = tenant_host(source)
    identity = identity_terms(label)
    if not host or not valid_gov_url(evidence) or not identity:
        return False, 'missing qualifying .gov evidence or jurisdiction identity'
    try:
        final, ctype, raw = fetch(evidence)
        if not valid_gov_url(urllib.parse.urlunsplit(final)):
            return False, 'official evidence redirected outside .gov'
        if 'text/html' not in ctype.lower():
            return False, 'official evidence is not HTML'
        page = Page()
        page.feed(raw.decode('utf-8', 'replace'))
        links = [urllib.parse.urljoin(urllib.parse.urlunsplit(final), x) for x in page.links]
        if not any(tenant_host(link) == host for link in links):
            return False, 'official .gov page does not link exact Legistar tenant'
        text = ' '.join(html.unescape(x) for x in page.words).lower()
        text = re.sub(r'\s+', ' ', text)
        place, state = identity
        if place.lower() not in text or not re.search(r'\b' + re.escape(state.lower()) + r'\b', text):
            return False, 'jurisdiction name/state not established on .gov page'
        # Confirm tenant actually serves public Legistar API data.
        code = host.split('.')[0]
        api = 'https://webapi.legistar.com/v1/' + code + '/matters?%24top=1'
        final_api, _, data = fetch(api, {'User-Agent': UA, 'Accept': 'application/json'})
        if final_api.hostname != 'webapi.legistar.com' or not isinstance(json.loads(data), list):
            return False, 'Legistar API did not return a public matters list'
        return True, 'official .gov link and public Legistar API confirmed'
    except (ValueError, UnicodeError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, type(exc).__name__

def request_db(path, method='GET', payload=None):
    base = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key,
               'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
        headers['Prefer'] = 'return=minimal'
    req = urllib.request.Request(base + '/rest/v1/' + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read()) if method == 'GET' else res.status

def main():
    query = urllib.parse.urlencode({'select': 'source_url,evidence_url,jurisdiction_label,source_kind,verification_status',
                                    'source_kind': 'eq.legistar', 'verification_status': 'eq.candidate', 'limit': '100'})
    rows = request_db('government_source_registry?' + query)
    if not isinstance(rows, list):
        raise ValueError('unexpected Supabase registry response')
    print('Candidate Legistar sources checked:', len(rows))
    approved = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(verify, rows))
    for row, (ok, reason) in zip(rows, outcomes):
        print('Candidate:', str(row.get('source_url'))[:120], 'VERIFIED' if ok else 'REVIEW', reason)
        if not ok:
            continue
        # Conditional PATCH prevents promotion if status changed after our read.
        filters = urllib.parse.urlencode({'source_url': 'eq.' + row['source_url'],
                                          'verification_status': 'eq.candidate',
                                          'source_kind': 'eq.legistar'})
        request_db('government_source_registry?' + filters, 'PATCH', {'verification_status': 'verified'})
        approved += 1
    print('Source verification promotions attempted:', approved)
    print('Government agenda records auto-published: 0')

if __name__ == '__main__':
    main()
