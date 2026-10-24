import unittest
import contextlib
import io
from unittest.mock import patch
import auto_register_derived_gis as v

P={"source_key":"elpaso_co","source_status":"verified",
  "gis_layer_url":"https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer/1",
  "government_evidence_url":"https://admin.elpasoco.com/digital-strategy-and-technology/licensed-gis-data/",
  "jurisdiction_label":"El Paso County, CO",
  "bounds_south":38.55,"bounds_west":-105.3,"bounds_north":39.25,"bounds_east":-104.3}
R={"authority_key":"elpaso_co","verification_status":"verified",
   "government_gis_host":"gisservices.elpasoco.com",
   "official_government_page":P["government_evidence_url"],
   "allowed_layer_path":P["gis_layer_url"].split("gisservices.elpasoco.com")[1],
   "jurisdiction_label":"El Paso County, CO"}
C={"gis_layer_url":"https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/New_Flock_Cameras/MapServer/1",
  "layer_name":"Flock_Cameras","geometry_type":"esriGeometryPoint",
  "object_id_field":"OBJECTID","trust_status":"unverified"}
L={"name":"Flock_Cameras","type":"Feature Layer","geometryType":"esriGeometryPoint",
   "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"},{"name":"NAME","type":"esriFieldTypeString"}]}
S={"layers":[{"id":1,"name":"Flock_Cameras"}]}
IDS={"objectIdFieldName":"OBJECTID","objectIds":[5]}
Q={"features":[{"attributes":{"OBJECTID":5,"NAME":"Flock 5"},
                "geometry":{"x":-104.8,"y":38.9}}]}
class Derivation(unittest.TestCase):
 def test_parent_must_match_exact_reviewed_government_layer(self):
  with patch.object(v,"api_request",side_effect=[
   [P],[R],[C]]):
   results=list(v.discovery_inputs())
  self.assertEqual(len(results),1)
  with patch.object(v,"api_request",side_effect=[
   [{**P,"government_evidence_url":"https://evil.example/fake"}],[R],[C]]):
   with self.assertRaises(ValueError):list(v.discovery_inputs())
 def test_original_gis_schema_and_bounded_points(self):
  with patch.object(v,"get_official_json",side_effect=[S,L,IDS,Q,IDS]):
   proof=v.verify_layer(P,R,C)
  self.assertEqual(proof["p_locations"],[{"id":5,"lat":38.9,"lon":-104.8}])
  self.assertTrue(proof["p_source_key"].startswith("gis_elpaso_co_"))
 def test_ambiguous_and_empty_data_held(self):
  for data in ({"features":[]},
    {"features":[{"attributes":{"OBJECTID":5,"NAME":""},"geometry":{"x":-104.8,"y":38.9}}]},
    {"features":[{"attributes":{"OBJECTID":5,"NAME":"Flock"},"geometry":{"x":0,"y":38.9}}]}):
   with patch.object(v,"get_official_json",side_effect=[S,L,IDS,data,IDS]):
    with self.assertRaises(ValueError):v.verify_layer(P,R,C)
 def test_partial_or_mutating_original_camera_id_inventory_held(self):
  for responses in (
    [S,L,{"objectIds":[5,6]},Q,IDS],
    [S,L,IDS,Q,{"objectIds":[5,6]}],
    [S,L,{"objectIds":[5,5]},Q,IDS],
    [S,L,IDS,{"features":[]},IDS]):
   with self.subTest(case=responses):
    with patch.object(v,"get_official_json",side_effect=responses):
     with self.assertRaises(ValueError):v.verify_layer(P,R,C)
 def test_complete_inventory_is_explicitly_fetched_twice(self):
  queries=[]
  def get(url):
   queries.append(url)
   return [S,L,IDS,Q,IDS][len(queries)-1]
  with patch.object(v,"get_official_json",side_effect=get):
   v.verify_layer(P,R,C)
  self.assertEqual(sum("returnIdsOnly=true" in u for u in queries),2)
  self.assertTrue(any("objectIds=5" in u for u in queries))
 def test_offsite_gis_source_cannot_be_promoted(self):
  with patch.object(v,"get_official_json") as read:
   with self.assertRaises(ValueError):
    v.verify_layer(P,R,{**C,"gis_layer_url":"https://services.arcgis.com/Bad/arcgis/rest/services/Camera/FeatureServer/1"})
  read.assert_not_called()
 def test_no_registration_in_dryrun(self):
  with (patch.object(v,"discovery_inputs",return_value=[(P,R,C)]),
        patch.object(v,"verify_layer",return_value={"p_locations":[1]}),
        patch.object(v,"api_request") as db):
   result=v.run(dry_run=True)
  self.assertEqual(result["eligible_live_layers"],1)
  db.assert_not_called()
 def test_private_candidate_uri_never_written_to_public_workflow_log(self):
  output=io.StringIO()
  with (patch.object(v,"discovery_inputs",return_value=[(P,R,C)]),
        patch.object(v,"verify_layer",return_value={"p_locations":[1]}),
        contextlib.redirect_stdout(output)):
   v.run(dry_run=True)
  self.assertNotIn(C["gis_layer_url"],output.getvalue())
  self.assertIn("source_hash",output.getvalue())
 def test_untrusted_third_party_never_passes_input_screen(self):
  with patch.object(v,"api_request",side_effect=[
    [P],[R],[{**C,"gis_layer_url":"https://services.arcgis.com/Example/FeatureServer/0"}]]):
   self.assertEqual(list(v.discovery_inputs()),[])
if __name__=="__main__":
 unittest.main()
