"""Static release guard for immutable browser dependencies and private key leaks.

Never print the contents of suspected credentials or private configuration.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAGES=['index.html','submit.html','community-review.html','review.html',
       'records.html','accountability.html','analytics.html','privacy.html','methodology.html']
SDK='https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.118.0/dist/umd/supabase.min.js'
LEAFLET='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
DANGEROUS=[
 re.compile(r'sb_secret_[A-Za-z0-9_-]{8,}'),
 re.compile(r'(?:sk_live_|rk_live_)[A-Za-z0-9]{8,}'),
 re.compile(r'postgres(?:ql)?://[^\s\"\x27<>]+:[^\s\"\x27<>]+@'),
 re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 re.compile(r'(?i)service_role\s*[:=]\s*[\"\x27][A-Za-z0-9_-]{35,}'),
]
class Srcs(HTMLParser):
 def __init__(self):
  super().__init__();self.scripts=[];self.styles=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='script' and a.get('src'):self.scripts.append(a['src'])
  if tag=='link' and a.get('href'):self.styles.append(a['href'])

class StaticReleaseSafety(unittest.TestCase):
 def test_public_script_allowlist(self):
  for p in PAGES:
   with self.subTest(page=p):
    text=(ROOT/p).read_text(encoding='utf8')
    parsed=Srcs();parsed.feed(text)
    for src in parsed.scripts:
     self.assertTrue(src.startswith('./') or src in (SDK,LEAFLET),
        p+': unapproved external script')
     self.assertFalse(src.startswith('//'),'Protocol-relative remote script')
    if p in ('submit.html','community-review.html','review.html'):
     self.assertEqual(parsed.scripts.count(SDK),1,'Versioned Auth SDK missing')
    if p=='index.html':
     self.assertEqual(parsed.scripts.count(LEAFLET),1)
 def test_secret_keys_not_bundled_into_static_site(self):
  paths=[ROOT/'config.js',ROOT/'map.js',ROOT/'geoapify-adapter.js',
    ROOT/'routing-provider.js']+[ROOT/p for p in PAGES]
  for path in paths:
   text=path.read_text(encoding='utf8')
   for pattern in DANGEROUS:
    with self.subTest(path=path.name,rule=pattern.pattern[:20]):
     self.assertIsNone(pattern.search(text),'Private credential detected in static publication')
 def test_public_config_is_publishable_only(self):
  text=(ROOT/'config.js').read_text(encoding='utf8')
  self.assertRegex(text,r'supabasePublishableKey:\s*\x27sb_publishable_')
  self.assertNotIn('sb_secret_',text)
  self.assertIn("locationProvider: 'geoapify'",text)
 def test_private_photo_bucket_is_not_static_public_url(self):
  for p in ('submit.html','community-review.html'):
   source=(ROOT/p).read_text(encoding='utf8')
   self.assertNotIn('.getPublicUrl(',source)
   self.assertIn('katoptron-community-evidence',source)
 def test_withdrawal_photo_privacy_and_retry_contract(self):
  source=(ROOT/'submit.html').read_text(encoding='utf8')
  migration=(ROOT/'supabase/migrations/080_revoke_withdrawn_report_reviewer_photo_access.sql').read_text(encoding='utf8')
  qa=(ROOT/'scripts/test_community_storage_rls_production.sql').read_text(encoding='utf8')
  self.assertIn('async function removeOwnPhotoEvidence',source)
  self.assertIn('Retry photo deletion',source)
  self.assertIn("report.report_status!=='withdrawn'",source)
  self.assertIn("bucket.remove(",source)
  self.assertIn("bucket.list(",source)
  self.assertIn('katoptron_internal.active_report_photo(name)',migration)
  self.assertIn("s.report_status<>'withdrawn'",migration)
  self.assertIn('alter policy katoptron_reviewer_read_report_evidence',migration)
  self.assertIn('create or replace function public.community_report_attachment_paths',migration)
  self.assertIn('Withdrawn photo remains readable to an editorial reviewer',qa)
  self.assertIn('Reviewer may mint signed URLs for withdrawn report',qa)

if __name__=='__main__':unittest.main()
