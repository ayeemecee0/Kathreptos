import unittest
from unittest.mock import patch
import recheck_external_arcgis_endorsements as m
from discover_government_gis_links import Anchors

URL="https://services3.arcgis.com/ABC123/arcgis/rest/services/Flock_Cameras/FeatureServer/0"
R={"source_key":"ext_test","government_disclosure_url":"https://city.example.gov/flock",
   "gis_layer_url":URL,"original_page_sha256":"a"*64,
   "verification_status":"verified"}
def page(anchor=True):
 a=Anchors();a.feed("<h1>Official Flock Safety ALPR camera program</h1>"+
                   ('<a href="'+URL+'">Flock GIS cameras</a>' if anchor else
                    '<p>Camera map is no longer provided.</p>'))
 return a
class EndorsementRecheck(unittest.TestCase):
 def test_original_direct_link_survives(self):
  self.assertTrue(m.check(R,page(), "b"*64))
  self.assertFalse(m.check(R,page(False),"b"*64))
 def test_original_government_service_root_link_survives(self):
  direct_root=URL.rsplit("/",1)[0]
  a=Anchors()
  a.feed('<h1>Official Flock Safety ALPR cameras</h1>'
         '<a href="'+direct_root+'">Flock GIS map</a>')
  service_record={**R,"government_link_method":"government_page_direct_service_v1"}
  self.assertTrue(m.check(service_record,a,"c"*64))
  self.assertFalse(m.check({**service_record,
        "government_link_method":"government_page_direct_anchor_v1"},a,"c"*64))
  self.assertFalse(m.check(service_record,page(),"c"*64))
 def test_removed_official_link_revokes_exact_source_only(self):
  with (patch.object(m,"approved_external",return_value=[R]),
        patch.object(m,"fetch_government_page",
                     return_value=(page(False),"b"*64)),
        patch.object(m,"api_request",return_value=True) as api):
   result=m.run()
  self.assertEqual(result["revoked"],1)
  self.assertEqual(api.call_args.kwargs["payload"]["p_source_key"],"ext_test")
 def test_temporary_website_error_does_not_revoke(self):
  with (patch.object(m,"approved_external",return_value=[R]),
        patch.object(m,"fetch_government_page",side_effect=TimeoutError("network")),
        patch.object(m,"api_request") as api):
   result=m.run()
  self.assertEqual(result["errors"],1)
  api.assert_not_called()
 def test_dry_run_prevents_withdrawal(self):
  with (patch.object(m,"approved_external",return_value=[R]),
        patch.object(m,"fetch_government_page",
                     return_value=(page(False),"b"*64)),
        patch.object(m,"api_request") as api):
   result=m.run(True)
  self.assertEqual(result["revoked"],0)
  self.assertEqual(result["removed_from_original_source"],1)
  api.assert_not_called()
if __name__=="__main__":unittest.main()
