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
COUNTY={
 "source_key":"elpaso_co",
 "gis_layer_url":"https://gisservices.elpasoco.com/arcgis2/rest/services/Sheriff/NeighborhoodWatchGroups_FlockCCTVCameras_GISMap3_WFL1/MapServer/1",
 "government_evidence_url":"https://admin.elpasoco.com/digital-strategy-and-technology/licensed-gis-data/",
 "jurisdiction_label":"El Paso County, CO",
 "source_status":"verified","expected_camera_type_field":"FlockLayer",
 "expected_id_field":"OBJECTID","bounds_south":38.55,"bounds_north":39.25,
 "bounds_west":-105.3,"bounds_east":-104.3
}
def feature(oid=44,kind="Flock Safety Falcon",lat=47.86,lon=-121.98):
 return {"attributes":{"OBJECTID":oid,"CameraType":kind},
         "geometry":{"x":lon,"y":lat}}
class GISVerification(unittest.TestCase):
 def test_county_source_matches_only_owner_bound_sheriff_layer(self):
  self.assertIsNotNone(gis.trusted_source(COUNTY))
  for alteration in (
      {"source_status":"candidate"},
      {"gis_layer_url":"https://services.arcgis.com/Random/FeatureServer/0"},
      {"government_evidence_url":"https://bad.example/government"},
      {"jurisdiction_label":"Elsewhere, CO"},
      {"bounds_east":-103}):
   self.assertIsNone(gis.trusted_source({**COUNTY,**alteration}))
 def test_county_exact_layer_qualifies_name_but_not_other_cameras(self):
  response={"features":[
    {"attributes":{"OBJECTID":3,"NAME":"FLK 003"},"geometry":{"x":-104.81,"y":38.9}},
    {"attributes":{"OBJECTID":4,"NAME":""},"geometry":{"x":-104.8,"y":38.9}},
    {"attributes":{"OBJECTID":5,"NAME":"FLK 005"},"geometry":{"x":-98.0,"y":38.9}}
  ]}
  rows,held,n=gis.decode_features(COUNTY,response)
  self.assertEqual(len(rows),1)
  self.assertTrue(rows[0]["record_key"].startswith("gis-elpaso_co-3-"))
  self.assertEqual(sum(held.values()),2)
 def test_county_metadata_cannot_be_reclassified_as_generic_traffic(self):
  meta={"mapName":"Flock Cameras GIS Map","documentInfo":{"Keywords":"El Paso County Sheriff Flock Safety"}}
  layer={"name":"Flock_Cameras","type":"Feature Layer","geometryType":"esriGeometryPoint",
         "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
  with patch.object(gis,"get_official_json",side_effect=[meta,layer,{"features":[]}]) as req:
   gis.gis_query(COUNTY)
  self.assertEqual(req.call_count,3)
  with patch.object(gis,"get_official_json",side_effect=[meta,{**layer,"name":"Traffic_Cameras"}]) as req:
   with self.assertRaises(ValueError):
    gis.gis_query(COUNTY)
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
        patch.object(gis,"mark_rechecked") as recheck,
        patch.object(gis,"revoke_stale") as revoke):
   out=gis.sync(dry_run=True)
  self.assertEqual(out["eligible"],1)
  save.assert_not_called()
  recheck.assert_not_called()
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
 def test_rechecked_records_refresh_timestamp_without_rewriting_facts(self):
  with (patch.object(gis,"fetch_verified_sources",return_value=[SOURCE]),
        patch.object(gis,"gis_query",return_value={"features":[feature()]}),
        patch.object(gis,"write_verified",return_value=False),
        patch.object(gis,"mark_rechecked") as recheck,
        patch.object(gis,"fetch_existing",return_value=[])):
   out=gis.sync()
  self.assertEqual(out["rechecked"],1)
  recheck.assert_called_once()
 def test_empty_inventory_does_not_revoke(self):
  with (patch.object(gis,"fetch_verified_sources",return_value=[SOURCE]),
        patch.object(gis,"gis_query",return_value={"features":[]}),
        patch.object(gis,"revoke_stale") as revoke):
   self.assertEqual(gis.sync()["errors"],1)
  revoke.assert_not_called()
if __name__=="__main__": unittest.main()
