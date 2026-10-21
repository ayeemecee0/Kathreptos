"""Safeguards for automatic original-government GIS Flock camera detection."""
import unittest
from unittest.mock import patch
import auto_verify_camera_gis as gis

SOURCE={
 "source_key":"monroe_wa",
 "gis_layer_url":"https://gis.monroewa.gov/citygis/rest/services/UtilityData/Street_Layers/MapServer/22",
 "government_evidence_url":"https://monroewa.gov/1324/Flock-Safety-Camera-Program",
 "jurisdiction_label":"Monroe, WA",
 "source_status":"verified","expected_camera_type_field":"CameraType",
 "expected_id_field":"OBJECTID","bounds_south":47.80,"bounds_north":48.00,
 "bounds_west":-122.12,"bounds_east":-121.80,
}
def feature(oid=44,kind="Flock Safety Falcon",lat=47.86,lon=-121.98):
 return {"attributes":{"OBJECTID":oid,"CameraType":kind},
         "geometry":{"x":lon,"y":lat}}
class GISVerification(unittest.TestCase):
 def test_exact_authority_binding(self):
  self.assertIsNotNone(gis.trusted_source(SOURCE))
  for bad in ({"source_key":"unreviewed"},{"source_status":"candidate"},
              {"jurisdiction_label":"Not Monroe"},{"bounds_north":52},
              {"gis_layer_url":"https://evil.example/query"}):
   self.assertIsNone(gis.trusted_source({**SOURCE,**bad}))
 def test_manufacturer_and_device_class(self):
  for val in ("Flock Safety","Flock Falcon ALPR","Flock Safety Falcon"):
   self.assertTrue(gis.classify_camera_type(val),val)
  for val in ("Other ALPR","Flock Raven","Flock Gunshot Detector",
              "Flock Condor","Traffic camera",None):
   self.assertFalse(gis.classify_camera_type(val),val)
 def test_exact_coordinates_and_provenance(self):
  rows,held,n=gis.decode_features(SOURCE,{"features":[feature()]})
  self.assertEqual(len(rows),1)
  r=rows[0]
  self.assertEqual((r["latitude"],r["longitude"]),(47.86,-121.98))
  self.assertEqual(r["location_accuracy"],"exact")
  self.assertEqual(r["verification_method"],"official_georeferenced_camera_record_v1")
  self.assertTrue(r["record_key"].startswith("gis-monroe_wa-44-"))
  self.assertEqual(len(r["evidence_sha256"]),64)
 def test_conflicts_and_other_vendors_are_held(self):
  rows,held,n=gis.decode_features(SOURCE,{"features":[
   feature(1),feature(1,lat=47.89),feature(2,kind="Motorola"),
   feature(3,lon=-120),feature(4,kind="Flock Raven")]})
  self.assertEqual(len(rows),1)
  self.assertEqual(sum(held.values()),4)
 def test_truncated_or_missing_gis_holds_everything(self):
  for payload in ({"features":[]},{"error":{"code":500}},
                  {"features":[feature()],"exceededTransferLimit":True},
                  {"features":[feature()]*1001}):
   with self.assertRaises(ValueError):
    gis.decode_features(SOURCE,payload)
 def test_dry_run_does_not_write_or_revoke(self):
  with (patch.object(gis,"fetch_verified_sources",return_value=[SOURCE]),
        patch.object(gis,"gis_query",return_value={"features":[feature()]}),
        patch.object(gis,"write_verified") as save,
        patch.object(gis,"revoke_stale") as revoke):
   out=gis.sync(dry_run=True)
  self.assertEqual(out["eligible"],1)
  save.assert_not_called()
  revoke.assert_not_called()
 def test_only_complete_updated_inventory_can_revoke(self):
  with (patch.object(gis,"fetch_verified_sources",return_value=[SOURCE]),
        patch.object(gis,"gis_query",return_value={"features":[feature()]}),
        patch.object(gis,"write_verified",return_value=True),
        patch.object(gis,"fetch_existing",return_value=[
          {"record_key":"gis-monroe_wa-77-"+"b"*12}]),
        patch.object(gis,"revoke_stale",return_value=True) as revoke):
   out=gis.sync()
  self.assertEqual(out["revoked"],1)
  revoke.assert_called_once()
 def test_empty_inventory_does_not_revoke(self):
  with (patch.object(gis,"fetch_verified_sources",return_value=[SOURCE]),
        patch.object(gis,"gis_query",return_value={"features":[]}),
        patch.object(gis,"revoke_stale") as revoke):
   self.assertEqual(gis.sync()["errors"],1)
  revoke.assert_not_called()
if __name__=="__main__": unittest.main()
