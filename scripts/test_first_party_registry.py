"""Offline checks for vetted first-party government GIS registry inputs."""
import unittest
from unittest.mock import patch
import first_party_registry as r

GOOD=r.load_sources()[0]

class ReviewRegistry(unittest.TestCase):
 def test_current_approved_source_parses(self):
  self.assertEqual(GOOD['source_key'],'agency_alachua_fl')
  self.assertEqual(r.validate_source(GOOD),GOOD)
  self.assertEqual(r.original_domain('maps.alachuacounty.us'),'alachuacounty.us')
 def test_registry_matches_exact_layer_and_shared_original_domain(self):
  invalid=[
   {**GOOD,'layer':'https://services.arcgis.com/x/FeatureServer/0'},
   {**GOOD,'original_gis_page':'http://growth-management.alachuacounty.us/GIS'},
   {**GOOD,'public_gis_anchor':'https://mapgenius.alachuacounty.us/?redirect=x'},
   {**GOOD,'layer':'https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer'},
   {**GOOD,'bounds_west':-180.1},
   {**GOOD,'bounds_north':90},
   {**GOOD,'bounds_east':-60},
   {**GOOD,'bounds_south':29.4,'bounds_north':29.3},
   {**GOOD,'review_basis':'some map has cameras'},
   {**GOOD,'source_key':'agency../superuser'},
   {**GOOD,'evil_override':'self approving'},
  ]
  for row in invalid:
   with self.subTest(row=str(row)[:70]),self.assertRaises(ValueError):
    r.validate_source(row)
 def test_registry_duplicate_source_or_layer_fails(self):
  with patch.object(r.FILE.__class__,'read_text',return_value=__import__('json').dumps([GOOD,GOOD])):
   with self.assertRaisesRegex(ValueError,'Duplicate'):
    r.load_sources()
 def test_no_empty_or_mass_unreviewed_registry(self):
  for rows in ([],[GOOD]*101):
   with patch.object(r.FILE.__class__,'read_text',return_value=__import__('json').dumps(rows)):
    with self.assertRaisesRegex(ValueError,'No valid'):
     r.load_sources()
 def test_government_host_is_required_not_arbitrary_map_provider(self):
  for bad in ('127.0.0.1','localhost','169.254.0.1'):
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):
     r.validate_source({**GOOD,'layer':
       'https://'+bad+'/server/rest/services/Flock_Cameras/FeatureServer/0'})
 def test_registry_is_metadata_only_not_a_public_camera_feed(self):
  self.assertNotIn('coordinates',GOOD)
  self.assertNotIn('points',GOOD)
  self.assertNotIn('latitude',GOOD)
  self.assertNotIn('longitude',GOOD)
if __name__=='__main__':unittest.main()
