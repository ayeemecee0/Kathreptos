"""Candidate source discovery never confers official GIS authority."""
import unittest
from unittest.mock import patch
import discover_camera_gis_sources as d
from auto_verify_camera_gis import trusted_source

class SourceDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.seed=d.SEEDS[0]
        self.layer={
          "name":"Flock Cameras",
          "type":"Feature Layer",
          "geometryType":"esriGeometryPoint",
          "objectIdField":"OBJECTID",
          "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}],
        }
    def test_pinned_host_point_layer_kept_private(self):
        item=d.candidate_from_metadata(self.seed,self.layer)
        self.assertEqual(item["trust_status"],"unverified")
        self.assertIn("does NOT establish",item["layer_purpose"])
        self.assertIsNone(trusted_source(item))
    def test_unknown_endpoints_cannot_be_discovered(self):
        with self.assertRaises(ValueError):
            d.candidate_from_metadata({"url":"https://evil.example/Layer/0"},self.layer)
    def test_ambiguous_layers_hold(self):
        for updates in (
            {"name":"Traffic Cameras"},
            {"type":"Table"},
            {"geometryType":"esriGeometryPolygon"},
            {"objectIdField":"UserId"},
            {"fields":[]},
            {"error":{"code":403}},
        ):
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    d.candidate_from_metadata(self.seed,{**self.layer,**updates})
    def test_only_private_queue_insert(self):
        with patch.object(d,"api_request",return_value=None) as req:
            d.stage_candidate(d.candidate_from_metadata(self.seed,self.layer))
        self.assertIn("flock_gis_source_candidates",req.call_args.args[0])
        self.assertNotIn("trusted_flock_gis_sources",req.call_args.args[0])
        self.assertIn("ignore-duplicates",req.call_args.kwargs["prefer"])
    def test_scan_dryrun_does_not_write(self):
        with (patch.object(d,"get_official_json",return_value=self.layer),
              patch.object(d,"stage_candidate") as write):
            r=d.scan(dry_run=True)
        self.assertEqual(r["qualified_leads"],len(d.SEEDS))
        write.assert_not_called()

if __name__=="__main__":
    unittest.main()
