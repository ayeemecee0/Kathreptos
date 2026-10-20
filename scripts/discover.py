"""Discover Flock-related public news leads; never automatically publish as verified facts."""
import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

QUERIES = [
    '"Flock Safety" city council contract',
    '"Flock Safety" police department vote',
    '"Flock Safety" contract terminated',
    '"Flock Safety" public records',
]

def fetch_candidates():
    import feedparser
    out = {}
    for query in QUERIES:
        url = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(query) + '&hl=en-US&gl=US&ceid=US:en'
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get('title', '')
            if not re.search(r'flock', title, re.I):
                continue
            link = entry.get('link', '')
            if not link.startswith('https://'):
                continue
            source = entry.get('source', {})
            out[link] = {
                'url': link,
                'headline': title[:500],
                'publisher': source.get('title', '') if hasattr(source, 'get') else '',
                'snippet': re.sub('<[^>]+>', '', entry.get('summary', ''))[:1200],
                'discovered_at': datetime.now(timezone.utc).isoformat(),
                'status': 'unreviewed',
            }
    return list(out.values())

def submit(rows, url, key):
    endpoint = url.rstrip('/') + '/rest/v1/discovery_queue?on_conflict=url'
    data = json.dumps([{k: v for k, v in row.items() if k in ('url', 'headline', 'publisher', 'snippet', 'status')} for row in rows]).encode()
    request = urllib.request.Request(
        endpoint, data=data, method='POST',
        headers={'apikey': key, 'Authorization': 'Bearer ' + key,
                 'Content-Type': 'application/json',
                 'Prefer': 'resolution=ignore-duplicates,return=minimal'},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='candidates.json')
    parser.add_argument('--supabase-url', default=os.getenv('SUPABASE_URL'))
    parser.add_argument('--service-key', default=os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
    args = parser.parse_args()
    rows = fetch_candidates()
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2)
    print(f'{len(rows)} unverified leads saved to {args.output}')
    if args.supabase_url and args.service_key and rows:
        print('Review queue HTTP status:', submit(rows, args.supabase_url, args.service_key))
