import unittest
from unittest.mock import patch
import audit_external_arcgis_candidates as a

LAYER="https://services3.arcgis.com/0Uo0Kvp9YTHRegvR/arcgis/rest/services/Flock_Cameras_-_Public/FeatureServer/0"
CAND={"gis_layer_url":LAYER,"layer_name":"Flock Cameras",
      "object_id_field":"OBJECTID","geometry_type":"esriGeometryPoint"}
META={"name":"Flock Cameras","type":"Feature Layer",
      "geometryType":"esriGeometryPoint","objectIdField":"OBJECTID",
      "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
SERVICE={"layers":[{"id":0,"name":"Flock Cameras"}]}

class CandidateTriage(unittest.TestCase):
 def test_arcgis_metadata_does_not_create_government_authority(self):
  with patch.object(a,'get_official_json',side_effect=[META,SERVICE]):
   self.assertEqual(a.check_external(CAND,set(),set()),
     "verified_arcgis_metadata_only_missing_original_government_link")
 def test_direct_link_still_requires_independent_attestation(self):
  with patch.object(a,'get_official_json',side_effect=[META,SERVICE]):
   self.assertEqual(a.check_external(CAND,{LAYER},set()),
     "candidate_government_link_needs_full_attestation")
 def test_mutated_metadata_is_held_even_with_government_link(self):
  with patch.object(a,'get_official_json',side_effect=[{**META,"name":"Traffic"},{"layers":[]}]):
   self.assertEqual(a.check_external(CAND,{LAYER},set()),
      "metadata_changed_or_not_point_camera_layer")
 def test_same_layer_does_not_publish_twice(self):
  with patch.object(a,'get_official_json') as get:
   self.assertEqual(a.check_external(CAND,set(),{LAYER}),
     "already_trusted_layer_review_duplicate")
   get.assert_not_called()
 def test_not_an_external_arcgis_cannot_be_auto_confirmed(self):
  with patch.object(a,'get_official_json') as get:
   self.assertEqual(a.check_external({**CAND,"gis_layer_url":"https://example.gov/a"},
                                  set(),set()),"not_external_arcgis")
   get.assert_not_called()
if __name__=="__main__":unittest.main()
