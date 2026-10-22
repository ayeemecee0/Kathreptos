"""Offline safeguards for Katoptron published-camera health monitoring."""
import datetime as dt
import unittest
import monitor_public_health as m

NOW=dt.datetime(2026,10,22,18,0,tzinfo=dt.timezone.utc)
def row(name,check=None,status='verified'):
 return {'jurisdiction_label':name,'verification_status':status,
         'location_accuracy':'exact','source_url':'https://agency.gov/camera',
         'last_source_recheck_at':(check or NOW).isoformat()}
class HealthTests(unittest.TestCase):
 def test_accepts_current_verified_evidence(self):
  rows=[row('Monroe, WA')]*18+[row('El Paso County, CO')]*16+[row('Peoria, AZ')]*74
  counts,last=m.assess(rows,now=NOW)
  self.assertEqual(sum(counts.values()),108)
 def test_withdrawn_gis_source_triggers_alert(self):
  with self.assertRaisesRegex(ValueError,'below baseline'):
   m.assess([row('Peoria, AZ')]*73,now=NOW,minimum={'Peoria, AZ':74})
 def test_stale_maintenance_alerts(self):
  with self.assertRaisesRegex(ValueError,'stale'):
   m.assess([row('Peoria, AZ',NOW-dt.timedelta(days=5))],
     now=NOW,minimum={'Peoria, AZ':1})
 def test_unverified_records_must_not_leak(self):
  with self.assertRaisesRegex(ValueError,'leaked'):
   m.assess([row('Peoria, AZ',status='revoked')],now=NOW,minimum={})
 def test_unsafe_browser_key_rejected(self):
  self.assertEqual(m.public_key("supabasePublishableKey: 'sb_publishable_public'"),
   'sb_publishable_public')
  with self.assertRaises(ValueError):
   m.public_key("supabasePublishableKey: 'sb_secret_do_not_use'")
if __name__=='__main__':unittest.main()
