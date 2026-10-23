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
  counts,last=m.assess(rows,now=NOW,minimum={'Monroe, WA':18,'El Paso County, CO':16,'Peoria, AZ':74})
  self.assertEqual(sum(counts.values()),108)
 def test_new_verified_sources_part_of_baseline(self):
  rows=([row('Monroe, WA')]*18+[row('El Paso County, CO')]*16+
        [row('Peoria, AZ')]*74+[row('Lawrenceville, GA')]*45+
        [row('Webster, TX')]*53+[row('Newport Beach, CA')]*69)
  counts,_=m.assess(rows,now=NOW)
  self.assertEqual(sum(counts.values()),275)
  self.assertEqual(counts['Webster, TX'],53)
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
 def test_public_summary_and_camera_inventory_must_agree(self):
  metrics=[{'verified_camera_points':275,'verified_point_jurisdictions':6,
            'verified_area_polygons':0,'approximate_location_records':0,
            'documented_government_programs':13}]
  self.assertEqual(m.assess_published_summary(metrics,{
    'Monroe, WA':18,'El Paso County, CO':16,'Peoria, AZ':74,
    'Lawrenceville, GA':45,'Webster, TX':53,
    'Newport Beach, CA':69
  })['verified_camera_points'],275)
  with self.assertRaisesRegex(ValueError,'differs'):
   m.assess_published_summary(metrics,{'Peoria, AZ':74})
 def test_state_index_separates_original_gis_pins_from_programs(self):
  rows=[
    {'state_code':'AZ','verified_camera_points':74,
     'verified_camera_jurisdictions':1,'dated_program_records':0,
     'terminated_program_records':0},
    {'state_code':'CA','verified_camera_points':0,
     'verified_camera_jurisdictions':0,'dated_program_records':3,
     'terminated_program_records':1}
  ]
  self.assertEqual(m.assess_state_evidence_index(rows,{'Peoria, AZ':74},3),2)
  with self.assertRaisesRegex(ValueError,'disclosures differ'):
   m.assess_state_evidence_index(rows,{'Peoria, AZ':74},4)
  with self.assertRaisesRegex(ValueError,'GIS camera totals differ'):
   m.assess_state_evidence_index(rows,{'Peoria, AZ':73},3)
  with self.assertRaisesRegex(ValueError,'without evidence'):
   m.assess_state_evidence_index([rows[0],
       {**rows[1],'dated_program_records':0,'terminated_program_records':0}],
       {'Peoria, AZ':74},0)
 def test_health_monitor_pages_before_claiming_complete(self):
  from unittest.mock import patch
  import json
  first=[{'record_key':str(i)} for i in range(80)]
  with patch.object(m,'get',side_effect=[json.dumps(first),json.dumps([{'record_key':'80'}])]) as fake:
   rows=m.fetch_public_camera_evidence('sb_publishable_testing')
  self.assertEqual(len(rows),81)
  self.assertIn('offset=80',fake.call_args_list[1].args[0])
 def test_unsafe_browser_key_rejected(self):
  self.assertEqual(m.public_key("supabasePublishableKey: 'sb_publishable_public'"),
   'sb_publishable_public')
  with self.assertRaises(ValueError):
   m.public_key("supabasePublishableKey: 'sb_secret_do_not_use'")
if __name__=='__main__':unittest.main()
