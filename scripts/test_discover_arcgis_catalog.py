import unittest
from unittest.mock import patch
import discover_arcgis_catalog as x

URL="https://services.arcgis.com/Acme0123/arcgis/rest/services/Flock_Cameras/FeatureServer"
ITEM={"title":"Flock Cameras","type":"Feature Service","url":URL,"tags":["Flock Safety"]}
META={"name":"Flock Cameras","type":"Feature Layer",
      "geometryType":"esriGeometryPoint","objectIdField":"OBJECTID",
      "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
class Catalog(unittest.TestCase):
 def test_only_public_esri_service_domain_no_arbitrary_urls(self):
  self.assertEqual(x.vetted_service_url(ITEM),URL)
  for url in ("https://evil.gov/fake/FeatureServer",
              "http://services.arcgis.com/foo/FeatureServer",
              "https://services.arcgis.com.evil.org/a/arcgis/rest/services/Flock/FeatureServer"):
   self.assertIsNone(x.vetted_service_url({**ITEM,"url":url}))
 def test_vendor_name_alone_remains_private(self):
  c=x.valid_candidate(URL+"/0",META)
  self.assertEqual(c["trust_status"],"unverified")
  self.assertIsNone(c["public_gov_context_url"])
  self.assertIn("NOT verified",c["layer_purpose"])
  self.assertIsNone(x.valid_candidate(URL+"/0",{**META,"geometryType":"esriGeometryPolygon"}))
 def test_dryrun_never_writes_or_verifies(self):
  with (patch.object(x,"public_search",return_value=[ITEM]),
        patch.object(x,"get_official_json",side_effect=[
          {"layers":[{"id":0,"name":"Flock Cameras"}]},META]*3),
        patch.object(x,"stage_candidate") as stage):
   out=x.scan(dry_run=True)
  self.assertEqual(out["qualified_private_leads"],1)
  stage.assert_not_called()
 def test_no_unverified_search_result_can_override_government_authority(self):
  with patch.object(x,"stage_candidate") as stage:
   stage({"gis_layer_url":URL+"/0"})
  self.assertEqual(stage.call_count,1)
  self.assertNotIn("trusted_flock_gis_sources",x.__doc__)
if __name__=="__main__":unittest.main()
