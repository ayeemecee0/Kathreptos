import unittest
from unittest.mock import patch
import recheck_auto_original_gov_gis as m
from discover_government_gis_links import Anchors

PAGE="https://police.city.example.gov/flock"
GIS="https://gis.city.example.gov/arcgis/rest/services/Flock/MapServer/7"
O={"source_key":"autogov_test","government_page_url":PAGE,
   "original_page_sha256":"a"*64}
C={"source_key":"autogov_test","gis_layer_url":GIS,
   "source_status":"verified"}
def html(link):
 d=Anchors()
 d.feed("<h1>Flock Safety ALPR camera GIS map</h1>"+
    ('<a href="'+GIS+'">Flock GIS camera map</a>' if link else
     "<p>Program changed.</p>"))
 return d
class AutoOriginalRecheck(unittest.TestCase):
 def test_live_source_hyperlink_has_to_match_exact_layer(self):
  self.assertTrue(m.original_link_present(html(True),PAGE,"b"*64,GIS))
  self.assertFalse(m.original_link_present(html(False),PAGE,"b"*64,GIS))
 def test_link_loss_revokes_only_specific_source(self):
  with (patch.object(m,"source_records",return_value=[(O,C)]),
        patch.object(m,"fetch_government_page",return_value=(html(False),"b"*64)),
        patch.object(m,"api_request",return_value=True) as api):
   result=m.run()
  self.assertEqual(result["sources_revoked"],1)
  self.assertEqual(api.call_args.kwargs["payload"]["p_source_key"],"autogov_test")
 def test_network_failure_never_retracts_verified_points(self):
  with (patch.object(m,"source_records",return_value=[(O,C)]),
        patch.object(m,"fetch_government_page",side_effect=TimeoutError("network")),
        patch.object(m,"api_request") as api):
   result=m.run()
  self.assertEqual(result["errors"],1)
  api.assert_not_called()
 def test_dryrun_does_not_remove_source(self):
  with (patch.object(m,"source_records",return_value=[(O,C)]),
        patch.object(m,"fetch_government_page",return_value=(html(False),"b"*64)),
        patch.object(m,"api_request") as api):
   result=m.run(True)
  self.assertEqual(result["sources_revoked"],0)
  api.assert_not_called()
if __name__=="__main__":unittest.main()
