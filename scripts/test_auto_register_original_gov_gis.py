import unittest
from unittest.mock import patch
import auto_register_original_gov_gis as x
from discover_government_gis_links import Anchors

PAGE="https://police.city.example.gov/flock"
URL="https://gis.city.example.gov/arcgis/rest/services/Flock_Cameras/MapServer/0"
LAYER={"name":"Flock Cameras","type":"Feature Layer",
       "geometryType":"esriGeometryPoint",
       "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"},
                 {"name":"CameraID","type":"esriFieldTypeString"}]}
SERVICE={"layers":[{"id":0,"name":"Flock Cameras"}]}
DATA={"features":[{"attributes":{"OBJECTID":4,"CameraID":"Camera 4"},
          "geometry":{"x":-98.45,"y":38.5}}]}
def doc():
 d=Anchors();d.feed("<h1>Our Flock Safety ALPR camera system</h1>"
   '<a href="'+URL+'">Flock Cameras GIS Map</a>')
 return d
class NewOriginalGov(unittest.TestCase):
 def test_same_government_apex_required(self):
  self.assertTrue(x.same_gov_apex(PAGE,URL))
  self.assertFalse(x.same_gov_apex(PAGE,URL.replace("gis.city.example.gov","gis.evil.gov")))
  self.assertFalse(x.same_gov_apex(PAGE,URL.replace("gis.city.example.gov","services.arcgis.com")))
  self.assertFalse(x.same_gov_apex(PAGE,"http://gis.city.example.gov/arcgis/rest/services/Map/MapServer/0"))
 def test_original_layer_flock_schema_and_geometry(self):
  with patch.object(x,"get_official_json",side_effect=[SERVICE,LAYER,DATA]):
   idfield,vendor,points,sha,candidate=x.qualified_original_layer(PAGE,URL)
  self.assertEqual(idfield,"CameraID")
  self.assertIsNone(vendor)
  self.assertEqual(points,[{"id":4,"lat":38.5,"lon":-98.45}])
  self.assertEqual(candidate["trust_status"],"unverified")
  with patch.object(x,"get_official_json",side_effect=[SERVICE,
         {**LAYER,"name":"General Traffic Cameras"},DATA]):
   with self.assertRaises(ValueError):
    x.qualified_original_layer(PAGE,URL)
 def test_unverified_and_stale_webpage_no_publication(self):
  with (patch.object(x,"private_government_pages",return_value=[
           {"page_url":PAGE,"page_sha256":"a"*64,"gis_links":[URL]}]),
        patch.object(x,"public_dns",return_value=True),
        patch.object(x,"fetch_government_page",return_value=(Anchors(),"b"*64)),
        patch.object(x,"qualified_original_layer") as verify,
        patch.object(x,"api_request") as api):
   out=x.run()
  self.assertEqual(out["registered"],0)
  verify.assert_not_called()
  api.assert_not_called()
 def test_changed_official_page_with_same_link_rechecks_digest(self):
  candidate={"gis_layer_url":URL,"layer_name":"Flock Cameras"}
  with (patch.object(x,"private_government_pages",return_value=[
          {"page_url":PAGE,"page_sha256":"a"*64,"gis_links":[URL]}]),
        patch.object(x,"public_dns",return_value=True),
        patch.object(x,"fetch_government_page",return_value=(doc(),"b"*64)),
        patch.object(x,"qualified_original_layer",return_value=[
          "CameraID",None,[{"id":4,"lat":38.5,"lon":-98.45}],"c"*64,candidate]),
        patch.object(x,"stage_candidate"),
        patch.object(x,"sync",return_value={"published":1,"errors":0}),
        patch.object(x,"api_request",return_value=True) as rpc):
   result=x.run()
  self.assertEqual(result["registered"],1)
  self.assertEqual(result["government_page_digest_refreshed"],1)
  self.assertEqual(rpc.call_args_list[0].kwargs["payload"]["p_expected_old_sha"],"a"*64)
 def test_dryrun_no_mutations(self):
  candidate={"gis_layer_url":URL,"layer_name":"Flock Cameras"}
  with (patch.object(x,"private_government_pages",return_value=[
          {"page_url":PAGE,"page_sha256":"a"*64,"gis_links":[URL]}]),
        patch.object(x,"public_dns",return_value=True),
        patch.object(x,"fetch_government_page",return_value=(doc(),"a"*64)),
        patch.object(x,"qualified_original_layer",return_value=[
          "CameraID",None,[{"id":4,"lat":38.5,"lon":-98.45}],"b"*64,candidate]),
        patch.object(x,"stage_candidate") as stage,
        patch.object(x,"api_request") as api):
   out=x.run(dry_run=True)
  self.assertEqual(out["qualified_live_layers"],1)
  stage.assert_not_called()
  api.assert_not_called()
if __name__=="__main__":unittest.main()
