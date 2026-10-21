"""Matching OSM reports to official GIS does not publish duplicate cameras."""
import unittest
from unittest.mock import patch
import match_camera_source_evidence as m

G={"source_key":"monroe_wa","gis_layer_url":"https://gis.monroewa.gov/citygis/rest/services/UtilityData/Street_Layers/MapServer/22"}
O=[{"record_key":"gis-monroe_wa-1-abc123","latitude":47.8584,"longitude":-121.9709,
    "source_url":G["gis_layer_url"],"location_accuracy":"exact"}]

class CrossSourceTests(unittest.TestCase):
    def test_nearby_independent_tag_matches_existing_government_point(self):
        evidence,issue=m.choose_match(
            {"candidate_key":"osm:node:42","latitude":47.8584,"longitude":-121.9709},O)
        self.assertIsNone(issue)
        self.assertEqual(evidence["verified_camera_key"],O[0]["record_key"])
        self.assertEqual(evidence["matching_method"],"trusted_gis_to_osm_30m_v1")
    def test_distant_report_never_matches(self):
        entry,why=m.choose_match(
          {"candidate_key":"osm:node:42","latitude":47.9,"longitude":-122.04},O)
        self.assertIsNone(entry)
        self.assertIn("no close",why)
    def test_ambiguous_multiple_cameras_held(self):
        points=O+[{"record_key":"gis-monroe_wa-2-x","latitude":47.8584,
                  "longitude":-121.97091}]
        item,why=m.choose_match(
          {"candidate_key":"osm:node:42","latitude":47.8584,"longitude":-121.9709},points)
        self.assertIsNone(item)
        self.assertIn("ambiguous",why)
    def test_no_public_write_ever(self):
        with patch.object(m,"api_request",return_value=None) as req:
            m.save_match({"candidate_key":"osm:node:42",
                         "verified_camera_key":"gis-monroe_wa-1-abc123",
                         "distance_m":0,"matching_method":"trusted_gis_to_osm_30m_v1"})
        self.assertIn("flock_camera_source_matches",req.call_args.args[0])
        self.assertNotIn("flock_camera_locations?",req.call_args.args[0])
    def test_dryrun_doesnt_store_any_match(self):
        with (patch.object(m,"fetch_verified_sources",return_value=[G]),
              patch.object(m,"official_points",return_value=O),
              patch.object(m,"candidate_points",return_value=[
                  {"candidate_key":"osm:node:42","latitude":47.8584,
                   "longitude":-121.9709}]),
              patch.object(m,"save_match") as store):
            c=m.run(dry_run=True)
        self.assertEqual(c["matched"],1)
        self.assertEqual(c["submitted"],0)
        store.assert_not_called()
    def test_region_query_has_two_sided_bounds(self):
        with patch.object(m,"api_request",return_value=[]) as req:
            m.candidate_points(O)
        q=req.call_args.args[0]
        self.assertIn("latitude=gte.",q)
        self.assertIn("&latitude=lte.",q)
        self.assertIn("&longitude=lte.",q)

if __name__=="__main__":
    unittest.main()
