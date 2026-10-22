"""Automatic government GIS link verification must stay government-anchored."""
import unittest
from unittest.mock import patch
import auto_link_gov_gis as link

ROOT={
"authority_key":"elpaso_co","government_gis_host":"gisservices.elpasoco.com",
"official_government_page":"https://admin.elpasoco.com/digital-strategy-and-technology/licensed-gis-data/",
"jurisdiction_label":"El Paso County, CO",
"allowed_layer_path":"/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer/1",
"expected_layer_name":"Flock_Cameras",
"bounds_south":38.55,"bounds_west":-105.3,"bounds_north":39.25,"bounds_east":-104.3,
"verification_status":"verified",
}
SOURCE={
"source_key":"elpaso_co","gis_layer_url":"https://gisservices.elpasoco.com"+ROOT["allowed_layer_path"],
"government_evidence_url":ROOT["official_government_page"],
"jurisdiction_label":"El Paso County, CO","expected_camera_type_field":"FlockLayer",
"expected_id_field":"OBJECTID","bounds_south":38.55,"bounds_west":-105.3,
"bounds_north":39.25,"bounds_east":-104.3,"source_status":"candidate",
}
LAYER={"name":"Flock_Cameras","type":"Feature Layer","geometryType":"esriGeometryPoint",
"fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"},{"name":"NAME","type":"esriFieldTypeString"}]}
SERVICE={"mapName":"Flock CCTV Camera GIS Map","documentInfo":{"Keywords":"Flock Safety cameras, El Paso County Sheriff"}}
FEATURES={"features":[{"attributes":{"OBJECTID":2,"NAME":"FLK 002"},"geometry":{"x":-104.8,"y":38.9}}]}

class AutoLinkTests(unittest.TestCase):
 def test_owned_host_and_exact_layer_required(self):
  self.assertIsNone(link.ensure_authority(SOURCE,ROOT))
  for edit in (
     {"gis_layer_url":"https://services.arcgis.com/evil/FeatureServer/0"},
     {"gis_layer_url":SOURCE["gis_layer_url"]+"/../2"},
     {"government_evidence_url":"https://evil.example/flock"},
     {"bounds_north":42.4},
     {"source_status":"verified"},
     {"expected_camera_type_field":"CameraType"},
  ):
   with self.subTest(edit=edit):
    with self.assertRaises(ValueError):
     link.ensure_authority({**SOURCE,**edit},ROOT)
 def test_live_gis_metadata_and_count(self):
  with (patch.object(link,"read_official_government_page",return_value=True),
        patch.object(link,"get_official_json",side_effect=[SERVICE,LAYER,FEATURES])):
   proof,n=link.metadata_proof(SOURCE,ROOT)
  self.assertEqual(n,1)
  self.assertEqual(proof["p_source_key"],"elpaso_co")
  self.assertEqual(len(proof["p_layer_sha"]),64)
 def test_forged_layer_vendor_or_polygon_held(self):
  for wrong in (
    {**LAYER,"name":"ALPR Cameras"},
    {**LAYER,"geometryType":"esriGeometryPolygon"},
    {**LAYER,"fields":[]},
  ):
   with (patch.object(link,"read_official_government_page",return_value=True),
         patch.object(link,"get_official_json",side_effect=[SERVICE,wrong,FEATURES])):
    with self.assertRaises(ValueError):
     link.metadata_proof(SOURCE,ROOT)
 def test_source_government_page_required(self):
  with patch.object(link,"read_official_government_page",side_effect=ValueError("unauthorized")):
   with self.assertRaises(ValueError):
    link.metadata_proof(SOURCE,ROOT)
 def test_no_promotion_without_verified_live_evidence(self):
  with (patch.object(link,"get_source_candidates",return_value=[(SOURCE,ROOT)]),
        patch.object(link,"metadata_proof",side_effect=ValueError("not verified")),
        patch.object(link,"api_request") as rpc):
   result=link.run()
  self.assertEqual(result["promoted"],0)
  rpc.assert_not_called()
 def test_dryrun_never_approves(self):
  with (patch.object(link,"get_source_candidates",return_value=[(SOURCE,ROOT)]),
        patch.object(link,"metadata_proof",return_value=({"p_source_key":"elpaso_co","p_layer_sha":"a"*64,"p_service_sha":"b"*64},7)),
        patch.object(link,"api_request") as rpc):
   result=link.run(dry_run=True)
  self.assertEqual(result["verified_live"],1)
  self.assertEqual(result["promoted"],0)
  rpc.assert_not_called()

if __name__=="__main__":unittest.main()
