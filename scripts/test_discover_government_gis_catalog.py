import unittest
from unittest.mock import patch
import discover_government_gis_catalog as d
R={"authority_key":"peoria_az","verification_status":"verified",
"government_gis_host":"gis.peoriaaz.gov",
"official_government_page":"https://devservices.peoriaaz.gov/devservices",
"allowed_layer_path":"/arcgis/rest/services/PM/pmPublicWorks/MapServer/286"}
class Catalog(unittest.TestCase):
 def test_only_owner_bound_gis_root(self):
  self.assertEqual(d.owner_prefix(R),"https://gis.peoriaaz.gov/arcgis/rest/services")
  with self.assertRaises(ValueError):d.owner_prefix({**R,"verification_status":"revoked"})
  with self.assertRaises(ValueError):d.owner_prefix({**R,"allowed_layer_path":"/private/read-secret"})
 def test_flock_point_only(self):
  service="https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer"
  meta={"layers":[{"id":286,"name":"Flock Cameras"},{"id":22,"name":"Traffic Cameras"}]}
  self.assertEqual(d.candidates_from_service(R,service,meta),[(286,"Flock Cameras")])
  feature={"name":"Flock Cameras","type":"Feature Layer",
           "geometryType":"esriGeometryPoint","objectIdField":"OBJECTID",
           "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
  result=d.qualify_layer(R,service,286,"Flock Cameras",feature)
  self.assertEqual(result["trust_status"],"unverified")
  self.assertIn("PRIVATE discovery lead",result["layer_purpose"])
  self.assertIsNone(d.qualify_layer(R,service,286,"Flock Cameras",
       {**feature,"geometryType":"esriGeometryPolygon"}))
 def test_no_candidate_is_published(self):
  service="https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer"
  listing={"folders":[],"services":[{"name":"PM/pmPublicWorks","type":"MapServer"}]}
  layers={"layers":[{"id":286,"name":"Flock Cameras"}]}
  layer={"name":"Flock Cameras","type":"Feature Layer","geometryType":"esriGeometryPoint",
         "objectIdField":"OBJECTID","fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
  with (patch.object(d,"verified_roots",return_value=[R]),
        patch.object(d,"get_official_json",side_effect=[listing,layers,layer]),
        patch.object(d,"stage_candidate") as stage):
   output=d.scan(dry_run=True,day=0)
  self.assertEqual(output["flock_layer_candidates"],1)
  stage.assert_not_called()
if __name__=="__main__":unittest.main()
