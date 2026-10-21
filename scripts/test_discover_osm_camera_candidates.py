"""Unverified OSM Flock ALPR candidate scanner must never publish map records."""
import unittest
from unittest.mock import patch
import discover_osm_camera_candidates as osm

def point(oid=1312,brand="Flock Safety",kind="node",lat=39.2,lon=-97.3):
 return {"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
  "properties":{"osmId":oid,"osmType":kind,"brand":brand}}

class PublicDatasetTests(unittest.TestCase):
 def test_explicit_flock_only_and_no_way_centroids(self):
  item=osm.candidate_from_feature(point())
  self.assertEqual(item["source_kind"],"osm_public_dataset")
  self.assertEqual(item["candidate_key"],"osm:node:1312")
  self.assertIn("NOT proof",item["evidence_excerpt"])
  for bad in (
    point(brand="Motorola Solutions"),point(brand="FlockHopper map"),
    point(kind="way"),point(lat=12),point(lon=-50),
    {**point(), "geometry":{"type":"Polygon","coordinates":[]}},
    {**point(),"properties":{"osmId":"1312","osmType":"node","brand":"Flock Safety"}},
  ):
   self.assertIsNone(osm.candidate_from_feature(bad))
 def test_private_staging_after_integrity_floor_only(self):
  # A partial national dataset cannot touch the private queue.
  with patch.object(osm,"upload_batch") as upload:
   with self.assertRaises(ValueError):
    osm.scan_features([point(oid=n) for n in range(1000)],shard=0)
  upload.assert_not_called()
 def test_full_dataset_shards_and_bounds(self):
  events=[point(oid=i) for i in range(1,50002)]
  with patch.object(osm,"upload_batch",side_effect=lambda rows:len(rows)) as save:
   result=osm.scan_features(events,shard=3)
  self.assertEqual(result["seen"],50001)
  self.assertGreater(result["staged"],1000)
  self.assertLessEqual(result["staged"],osm.MAX_CANDIDATES_PER_RUN)
  self.assertEqual(result["submitted"],result["staged"])
  self.assertTrue(save.called)
  for call in save.call_args_list:
   for row in call.args[0]:
    self.assertEqual(int(row["source_external_id"])%osm.SHARDS,3)
    self.assertEqual(row["source_kind"],"osm_public_dataset")
 def test_dryrun_does_not_write(self):
  with patch.object(osm,"upload_batch") as write:
   output=osm.scan_features([point(oid=n) for n in range(1,50002)],shard=2,dry_run=True)
  self.assertEqual(output["submitted"],0)
  self.assertGreater(output["staged"],0)
  write.assert_not_called()
 def test_upsert_never_promotes_to_verified(self):
  with patch.object(osm,"api_request",return_value=None) as request:
   self.assertEqual(osm.upload_batch([osm.candidate_from_feature(point())]),1)
  self.assertEqual(request.call_args.kwargs["method"],"POST")
  self.assertIn("ignore-duplicates",request.call_args.kwargs["prefer"])
  self.assertIn("return=minimal",request.call_args.kwargs["prefer"])
  self.assertNotIn("flock_camera_locations",request.call_args.args[0])
 def test_rejects_bad_shard(self):
  with self.assertRaises(ValueError):
   osm.scan_features([],shard=30)
if __name__=="__main__":unittest.main()
