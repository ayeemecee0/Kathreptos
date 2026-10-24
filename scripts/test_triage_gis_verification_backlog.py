"""Offline proof that candidate triage never promotes or miscounts public cameras."""
import contextlib
import io
import unittest
from unittest.mock import patch
import triage_gis_verification_backlog as q

PARENT={'source_key':'elpaso_co','jurisdiction_label':'El Paso County, CO'}
ROOT={'government_gis_host':'gisservices.elpasoco.com'}
URL='https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/FlockCameras/MapServer/1'
C={'gis_layer_url':URL,'public_gov_context_url':'https://admin.elpasoco.com/gis',
   'layer_name':'Flock_Cameras'}
EXTERNAL={'gis_layer_url':'https://services3.arcgis.com/safe/arcgis/rest/services/Flock_Cameras/FeatureServer/1',
          'public_gov_context_url':None}
KNOWN=[{'jurisdiction_label':'El Paso County, CO','latitude':38.9,'longitude':-104.8}]
MATCH={URL:(PARENT,ROOT,C)}

class Triage(unittest.TestCase):
 def test_duplicate_source_is_not_counted_again(self):
    kind,n,near=q.classify(C,{URL},{ROOT['government_gis_host']},MATCH,KNOWN)
    self.assertEqual((kind,n,near),('already_authorized_source_candidate_duplicate',0,0))
 def test_trusted_host_all_camera_points_near_existing_hold(self):
    with patch.object(q,'verify_layer',return_value={'p_locations':[
      {'lat':38.9,'lon':-104.8}]} ) as check:
      kind,n,close=q.classify(C,set(),{ROOT['government_gis_host']},MATCH,KNOWN,check)
    self.assertEqual(kind,'trusted_host_all_points_possible_overlaps_hold')
    self.assertEqual((n,close),(1,1))
 def test_trusted_host_mixed_camera_locations_held(self):
    def verify(*args):
      return {'p_locations':[{'lat':38.9,'lon':-104.8},
                             {'lat':39.01,'lon':-104.6}]}
    kind,n,close=q.classify(C,set(),{ROOT['government_gis_host']},MATCH,KNOWN,verify)
    self.assertEqual(kind,'trusted_host_mixed_new_and_possible_overlaps_hold')
    self.assertEqual((n,close),(2,1))
 def test_trusted_host_distinct_camera_locations_flagged_for_existing_worker(self):
    def verify(*args):
      return {'p_locations':[{'lat':39.01,'lon':-104.6}]}
    kind,n,close=q.classify(C,set(),{ROOT['government_gis_host']},MATCH,KNOWN,verify)
    self.assertEqual(kind,'trusted_host_distinct_points_eligible_for_existing_registration')
    self.assertEqual((n,close),(1,0))
 def test_external_arcgis_requires_original_agency_proof(self):
    with patch.object(q,'verify_layer') as fetch:
      state=q.classify(EXTERNAL,set(),{ROOT['government_gis_host']},{},KNOWN)
    self.assertEqual(state[0],'external_arcgis_needs_original_agency_endorsement')
    fetch.assert_not_called()
 def test_context_same_domain_does_not_approve_host(self):
    state=q.classify(C,set(),set(),{},KNOWN)
    self.assertEqual(state[0],'same_agency_domain_needs_publisher_review')
    self.assertEqual(state[1],0)
 def test_no_fake_publisher_proof_from_vendor(self):
    malicious={**EXTERNAL,'gis_layer_url':'https://other.example.com/Flock/FeatureServer/0'}
    state=q.classify(malicious,set(),set(),{},KNOWN)
    self.assertEqual(state[0],'unattributed_gis_source_needs_original_agency_proof')
    self.assertEqual(q.classify({**C,'gis_layer_url':'http://127.0.0.1/'},
       set(),set(),{},KNOWN)[0],'unsafe_or_invalid_source_url')
 def test_unreachable_trusted_original_host_held_without_promoting(self):
    def failed(*args):raise TimeoutError('Original GIS unavailable')
    state=q.classify(C,set(),{ROOT['government_gis_host']},MATCH,KNOWN,failed)
    self.assertEqual(state,('trusted_host_original_metadata_or_inventory_held',0,0))
 def test_original_geometry_overlap_distance(self):
    self.assertTrue(q.near((38.9,-104.8),(38.9001,-104.8)))
    self.assertFalse(q.near((38.9,-104.8),(38.95,-104.8)))
    with self.assertRaises(ValueError):q.near((float('nan'),-104.8),(38.9,-104.8))
 def test_output_hashes_private_urls_and_never_queries_third_party(self):
    with (patch.object(q,'inputs',return_value=([C,EXTERNAL],
             [],[{'government_gis_host':ROOT['government_gis_host']}],KNOWN,[])),
          patch.object(q,'discovery_inputs',return_value=[(PARENT,ROOT,C)]),
          patch.object(q,'verify_layer',return_value={'p_locations':[{'lat':38.9,'lon':-104.8}]})):
       # The runtime default argument was bound at definition; inject through
       # a wrapper so no real GIS network can run even in a test.
       original=q.classify
       def patched(*a,**kw):
          kw['check']=lambda *x:{'p_locations':[{'lat':38.9,'lon':-104.8}]}
          return original(*a,**kw)
       with patch.object(q,'classify',side_effect=patched),io.StringIO() as buffer:
          with contextlib.redirect_stdout(buffer):
              stats=q.run()
          printed=buffer.getvalue()
    self.assertEqual(stats['trusted_host_all_points_possible_overlaps_hold'],1)
    self.assertEqual(stats['external_arcgis_needs_original_agency_endorsement'],1)
    self.assertNotIn(URL,printed)
    self.assertNotIn(EXTERNAL['gis_layer_url'],printed)
    self.assertNotIn('38.9',printed)
    self.assertIn('NEW PUBLIC CAMERA LOCATIONS 0',printed)

if __name__=='__main__':unittest.main()
