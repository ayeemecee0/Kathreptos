import unittest
import contextlib
import io
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
IDS={"objectIdFieldName":"OBJECTID","objectIds":[4]}
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
  with patch.object(x,"get_official_json",side_effect=[SERVICE,LAYER,IDS,DATA,IDS]):
   idfield,vendor,points,sha,candidate=x.qualified_original_layer(PAGE,URL)
  self.assertEqual(idfield,"CameraID")
  self.assertIsNone(vendor)
  self.assertEqual(points,[{"id":4,"lat":38.5,"lon":-98.45}])
  self.assertEqual(candidate["trust_status"],"unverified")
  with patch.object(x,"get_official_json",side_effect=[SERVICE,
         {**LAYER,"name":"General Traffic Cameras"},IDS,DATA,IDS]):
   with self.assertRaises(ValueError):
    x.qualified_original_layer(PAGE,URL)
 def test_explicit_object_ids_detect_partial_and_changing_inventory(self):
  # Failing to receive all ObjectIDs must not silently publish a partial map.
  for responses in (
    [SERVICE,LAYER,{"objectIds":[4,5]},DATA],
    [SERVICE,LAYER,IDS,DATA,{"objectIds":[4,5]}],
    [SERVICE,LAYER,{"objectIds":[4,4]},DATA,IDS],
    [SERVICE,LAYER,IDS,{"features":[]},IDS],
  ):
   with self.subTest(case=len(responses)):
    with patch.object(x,"get_official_json",side_effect=responses):
     with self.assertRaises(ValueError):
      x.qualified_original_layer(PAGE,URL)
 def test_original_id_inventory_uses_explicit_object_id_query(self):
  urls=[]
  def read(url):
   urls.append(url)
   return [SERVICE,LAYER,IDS,DATA,IDS][len(urls)-1]
  with patch.object(x,"get_official_json",side_effect=read):
   x.qualified_original_layer(PAGE,URL)
  self.assertEqual(sum("returnIdsOnly=true" in url for url in urls),2)
  self.assertTrue(any("objectIds=4" in url for url in urls))
  self.assertFalse(any("resultRecordCount" in url for url in urls))
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
 def test_unambiguous_original_government_service_root(self):
  root=URL.rsplit("/",1)[0]
  with patch.object(x,"get_official_json",return_value={
    "layers":[{"id":0,"name":"Flock Cameras"},{"id":8,"name":"Traffic Cameras"}]}):
   self.assertEqual(x.resolve_exact_original_camera_layer(PAGE,root),
                    (URL,root,"Flock Cameras"))
  with patch.object(x,"get_official_json",return_value={
    "layers":[{"id":0,"name":"Flock Cameras"},{"id":1,"name":"Flock Cameras"}]}):
   with self.assertRaisesRegex(ValueError,"zero or multiple"):
    x.resolve_exact_original_camera_layer(PAGE,root)
 def test_government_service_root_never_resolves_untrusted_publisher(self):
  with patch.object(x,"get_official_json") as fetch:
   for url in ("http://gis.city.example.gov/arcgis/rest/services/Flock/MapServer",
      "https://services.arcgis.com/abc/arcgis/rest/services/Flock/FeatureServer",
      "https://gis.other.gov/arcgis/rest/services/Flock/MapServer"):
    with self.assertRaises(ValueError):
     x.resolve_exact_original_camera_layer(PAGE,url)
  fetch.assert_not_called()
 def test_government_service_direct_anchor_is_not_an_auto_approval(self):
  root=URL.rsplit("/",1)[0]
  doc=Anchors()
  doc.feed('<h1>Our Flock Safety ALPR camera system</h1>'
           '<a href="'+root+'">Flock GIS cameras</a>')
  candidate={"gis_layer_url":URL,"layer_name":"Flock Cameras"}
  with (patch.object(x,"private_government_pages",return_value=[
      {"page_url":PAGE,"page_sha256":'a'*64,"gis_links":[root]}]),
        patch.object(x,"get_official_json",return_value={
          "layers":[{"id":0,"name":"Flock Cameras"}]}),
        patch.object(x,"public_dns",return_value=True),
        patch.object(x,"fetch_government_page",return_value=(doc,'a'*64)),
        patch.object(x,"qualified_original_layer",return_value=[
          "CameraID",None,[{"id":4,"lat":38.5,"lon":-98.45}],'b'*64,candidate]),
        patch.object(x,"stage_candidate") as stage,
        patch.object(x,"api_request") as backend):
   result=x.run(dry_run=True)
  self.assertEqual(result["qualified_live_layers"],1)
  stage.assert_not_called()
  backend.assert_not_called()
 def test_private_candidate_link_not_printed_on_failed_source(self):
  output=io.StringIO()
  with (patch.object(x,"private_government_pages",return_value=[
           {"page_url":PAGE,"page_sha256":"a"*64,"gis_links":[URL]}]),
        patch.object(x,"resolve_exact_original_camera_layer",side_effect=ValueError("No original owner")),
        contextlib.redirect_stdout(output)):
   result=x.run(dry_run=True)
  self.assertEqual(result['held'],1)
  self.assertNotIn(URL,output.getvalue())
  self.assertIn('source_hash',output.getvalue())
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
