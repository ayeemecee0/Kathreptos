import unittest
from unittest.mock import patch
import auto_verify_camera_profiles as v
S={"source_key":"peoria_az","source_status":"verified",
"gis_layer_url":"https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer/286",
"government_evidence_url":"https://devservices.peoriaaz.gov/devservices/Cap/CapHome.aspx?TabName=HOME&module=Planning",
"jurisdiction_label":"Peoria, AZ","expected_id_field":"OBJECTID",
"bounds_south":33.2,"bounds_west":-113,"bounds_north":34.5,"bounds_east":-111.4}
P={"source_key":"peoria_az","profile_status":"verified","identity_mode":"official_flock_layer",
"vendor_field":None,"camera_id_field":"CameraID",
"expected_layer_name":"Flock Cameras","service_evidence_mode":"listed_flock_layer"}
R={"authority_key":"peoria_az","verification_status":"verified",
"government_gis_host":"gis.peoriaaz.gov","official_government_page":S["government_evidence_url"],
"allowed_layer_path":"/arcgis/rest/services/PM/pmPublicWorks/MapServer/286",
"jurisdiction_label":"Peoria, AZ"}
FIELDS=[{"name":"OBJECTID","type":"esriFieldTypeOID"},{"name":"CameraID","type":"esriFieldTypeString"}]
L={"name":"Flock Cameras","type":"Feature Layer","geometryType":"esriGeometryPoint","fields":FIELDS}
SERVICE={"layers":[{"id":286,"name":"Flock Cameras"}]}
def f(oid=3,lat=33.67,lon=-112.29,tag="P003"):
 return {"attributes":{"OBJECTID":oid,"CameraID":tag},"geometry":{"x":lon,"y":lat}}
class TestProfiles(unittest.TestCase):
 def test_reviewed_root_only(self):
  self.assertTrue(v.authorize(S,P,R))
  with self.assertRaises(ValueError):v.authorize(S,P,None)
  with self.assertRaises(ValueError):v.authorize({**S,"source_status":"candidate"},P,R)
  with self.assertRaises(ValueError):v.authorize({**S,"gis_layer_url":"https://evil.gov/MapServer/1"},P,R)
 def test_metadata_requires_original_flock_only_point_layer(self):
  v.check_metadata(S,P,SERVICE,L)
  with self.assertRaises(ValueError):
   v.check_metadata(S,P,SERVICE,{**L,"name":"Traffic Cameras"})
  with self.assertRaises(ValueError):
   v.check_metadata(S,P,{"layers":[]},L)
 def test_identified_points_only(self):
  rows,held,n=v.verify_points(S,P,{"features":[f(),f(4,tag=""),f(5,lon=0)]})
  self.assertEqual((len(rows),n),(1,3))
  self.assertEqual(sum(held.values()),2)
  self.assertEqual(rows[0]["location_accuracy"],"exact")
 def test_duplicate_government_id_not_published(self):
  with self.assertRaises(ValueError):
   v.verify_points(S,P,{"features":[f(),f()]})
 def test_lawrenceville_mixed_school_camera_exclusion(self):
  city={**S,"source_key":"lawrenceville_ga",
        "jurisdiction_label":"Lawrenceville, GA",
        "bounds_south":33.75,"bounds_west":-84.15,
        "bounds_north":34.1,"bounds_east":-83.85}
  policy={**P,"source_key":"lawrenceville_ga","vendor_field":"CameraType"}
  payload={"features":[
    {"attributes":{"OBJECTID":828,"CameraID":"1","CameraType":"PD Flock Camera"},
     "geometry":{"x":-83.97,"y":33.92}},
    {"attributes":{"OBJECTID":829,"CameraID":"2","CameraType":"PD School Camera"},
     "geometry":{"x":-83.99,"y":33.93}}]}
  rows,held,total=v.verify_points(city,policy,payload)
  self.assertEqual((len(rows),total),(1,2))
  self.assertEqual(held["not a Flock camera per original GIS field"],1)
  with self.assertRaises(ValueError):
   v.check_metadata(city,policy,SERVICE,L)
 def test_webster_city_vendor_stated_in_original_service(self):
  city={**S,"source_key":"webster_tx","jurisdiction_label":"Webster, TX"}
  policy={**P,"source_key":"webster_tx","expected_layer_name":"FLOCK Cameras - Webster PD",
          "camera_id_field":"ID","service_evidence_mode":"explicit_flock_service_text"}
  meta={"name":"FLOCK Cameras - Webster PD","type":"Feature Layer",
        "geometryType":"esriGeometryPoint",
        "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"},
                  {"name":"ID","type":"esriFieldTypeString"}]}
  service={"serviceDescription":"Webster PD Cameras (FLOCK) for reading vehicle license plates"}
  v.check_metadata(city,policy,service,meta)
  with self.assertRaises(ValueError):
   v.check_metadata(city,policy,{"serviceDescription":"Traffic cameras"},meta)
 def test_single_transient_original_government_gis_timeout_recovers(self):
  with (patch.object(v,"get_official_json",side_effect=[TimeoutError("original host slow"),{"features":[]}]) as fetch,
        patch.object(v.time,"sleep") as nap):
   data=v.resilient_government_gis_json("https://government.example.gov/MapServer/1?f=json")
  self.assertEqual(data,{"features":[]})
  self.assertEqual(fetch.call_count,2)
  nap.assert_called_once()
  with (patch.object(v,"get_official_json",side_effect=TimeoutError("source unavailable")),
        patch.object(v.time,"sleep")):
   with self.assertRaises(TimeoutError):
    v.resilient_government_gis_json("https://government.example.gov/MapServer/1?f=json")
 def test_government_endorsed_arcgis_requires_exact_verified_attestation(self):
  external={"source_key":"external_source","parent_source_key":"peoria_az",
    "gis_layer_url":"https://services3.arcgis.com/abcd1234/arcgis/rest/services/Flock_Cameras/FeatureServer/0",
    "government_disclosure_url":S["government_evidence_url"],
    "verification_status":"verified"}
  linked={**S,"source_key":"external_source",
    "gis_layer_url":external["gis_layer_url"]}
  self.assertTrue(v.authorize(linked,{**P,"source_key":"external_source"},None,external))
  with self.assertRaises(ValueError):
   v.authorize(linked,{**P,"source_key":"external_source"},None,
               {**external,"verification_status":"revoked"})
  with self.assertRaises(ValueError):
   v.authorize(linked,{**P,"source_key":"external_source"},None,
               {**external,"gis_layer_url":"https://evil.example/Fake/FeatureServer/1"})
 def test_transient_network_failure_retries_and_recovers(self):
  import urllib.error
  with (patch.object(v,"query_gis",side_effect=[
    urllib.error.URLError("timeout"),{"features":[f()]}]) as query,
    patch.object(v,"time") as sleep):
   rows,held,count=v.source_with_bounded_retries(S,P,attempts=2)
  self.assertEqual(count,1)
  self.assertEqual(query.call_count,2)
 def test_failed_network_retries_do_not_revoke(self):
  import urllib.error
  with (patch.object(v,"query_gis",side_effect=urllib.error.URLError("timeout")),
        patch.object(v,"revoke_stale") as revoke,
        patch.object(v,"time")):
   with self.assertRaises(RuntimeError):
    v.source_with_bounded_retries(S,P,attempts=2)
  revoke.assert_not_called()
 def test_dryrun_never_writes(self):
  with (patch.object(v,"approved_sources",return_value=[(S,P)]),
        patch.object(v,"query_gis",return_value={"features":[f()]}),
        patch.object(v,"write_verified") as save):
   result=v.sync(dry_run=True)
  self.assertEqual(result["eligible"],1)
  save.assert_not_called()
if __name__=="__main__":unittest.main()
