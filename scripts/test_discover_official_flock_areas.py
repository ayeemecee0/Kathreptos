import unittest
from unittest.mock import patch
import discover_official_flock_areas as g

R={"authority_key":"peoria_az","government_gis_host":"gis.peoriaaz.gov",
   "allowed_layer_path":"/arcgis/rest/services/PM/pmPublicWorks/MapServer/286",
   "verification_status":"verified"}
L={"name":"Flock Deployment Areas","type":"Feature Layer",
   "geometryType":"esriGeometryPolygon","objectIdField":"OBJECTID",
   "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
Q={"features":[{"attributes":{"OBJECTID":7},
                "geometry":{"rings":[[[-112.3,33.6],[-112.2,33.6],
                                       [-112.2,33.7],[-112.3,33.6]]]}}]}
class Areas(unittest.TestCase):
 def test_only_exact_original_host_and_named_flock_areas(self):
  with patch.object(g,"get_official_json",return_value={
      "layers":[{"id":5,"name":"Flock Deployment Areas"},
                {"id":6,"name":"Traffic Areas"}]}):
   items=list(g.polygon_layers(R))
  self.assertEqual(len(items),1)
  self.assertTrue(items[0][0].startswith("https://gis.peoriaaz.gov/"))
  with self.assertRaises(ValueError):
   list(g.polygon_layers({**R,"verification_status":"revoked"}))
 def test_government_catalog_one_transient_failure_recovers(self):
  with (patch.object(g,"get_official_json",side_effect=[
       {"error":{"code":503}},{"layers":[{"id":7,"name":"Flock Coverage Area"}]}]) as fetch,
        patch.object(g.time,"sleep") as snooze):
   out=list(g.polygon_layers(R))
  self.assertEqual(len(out),1)
  self.assertEqual(fetch.call_count,2)
  snooze.assert_called_once_with(0.4)
 def test_government_catalog_two_failures_still_fail_closed(self):
  with (patch.object(g,"get_official_json",side_effect=[
        {"error":{"code":503}},{"layers":None}]),
        patch.object(g.time,"sleep")):
   with self.assertRaisesRegex(ValueError,"after retry"):
    list(g.polygon_layers(R))
 def test_polygon_source_coordinates_are_used_unchanged(self):
  with patch.object(g,"get_official_json",side_effect=[L,Q]):
   rows=g.verify_polygon(R,"https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer/5",
                         "Flock Deployment Areas")
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["p_outline"],Q["features"][0]["geometry"]["rings"][0])
  self.assertTrue(rows[0]["p_area_key"].startswith("area_"))
 def test_multipart_or_missing_original_geometry_is_held(self):
  for geometry in ({"rings":[]},{"rings":Q["features"][0]["geometry"]["rings"]*2}):
   with patch.object(g,"get_official_json",side_effect=[L,{"features":[
      {"attributes":{"OBJECTID":7},"geometry":geometry}]}]):
    with self.assertRaises(ValueError):
     g.verify_polygon(R,"https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer/5",
                      "Flock Deployment Areas")
 def test_dryrun_never_publishes(self):
  with (patch.object(g,"approved_hosts",return_value=[R]),
        patch.object(g,"polygon_layers",return_value=[("https://gis.peoriaaz.gov/fake/MapServer/4","Flock Deployment Areas")]),
        patch.object(g,"verify_polygon",return_value=[{"p_area_key":"area_test"}]),
        patch.object(g,"api_request") as api):
   res=g.run(dry_run=True)
  self.assertEqual(res["original_gis_areas_qualified"],1)
  api.assert_not_called()
if __name__=="__main__":unittest.main()
