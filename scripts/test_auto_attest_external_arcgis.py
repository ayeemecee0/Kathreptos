import unittest
from unittest.mock import patch
import auto_attest_external_arcgis as v
from discover_government_gis_links import Anchors
SOURCE={"source_key":"peoria_az","source_status":"verified",
 "jurisdiction_label":"Peoria, AZ",
 "government_evidence_url":"https://city.example.gov/flock",
 "gis_layer_url":"https://gis.example.gov/arcgis/rest/services/Flock/MapServer/2",
 "bounds_south":33.2,"bounds_north":34.5,"bounds_west":-113,"bounds_east":-111.4}
ROOT={"authority_key":"peoria_az","verification_status":"verified",
 "government_gis_host":"gis.example.gov",
 "official_government_page":SOURCE["government_evidence_url"],
 "allowed_layer_path":"/arcgis/rest/services/Flock/MapServer/2",
 "jurisdiction_label":"Peoria, AZ"}
URL="https://services.arcgis.com/Abcde01234/arcgis/rest/services/Flock_Cameras/FeatureServer/0"
LINK={"gis_layer_url":URL,"disclosure_url":SOURCE["government_evidence_url"],
 "jurisdiction_label":"Peoria, AZ","layer_metadata_status":"unverified",
 "government_page_sha256":'a'*64,
 "discovery_method":"government_page_direct_anchor_v1"}
CANDIDATE={"gis_layer_url":URL,"layer_name":"Flock Cameras","geometry_type":"esriGeometryPoint",
           "object_id_field":"OBJECTID","trust_status":"unverified"}
ORGID="QWERTYUIOP123456"
SERVICE={"layers":[{"id":0,"name":"Flock Cameras"}]}
LAYER={"name":"Flock Cameras","type":"Feature Layer",
 "geometryType":"esriGeometryPoint",
 "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"},
           {"name":"CameraID","type":"esriFieldTypeString"}]}
POINTS={"features":[{"attributes":{"OBJECTID":7,"CameraID":"P-7"},
          "geometry":{"x":-112.2,"y":33.6}}]}
def doc():
 p=Anchors()
 p.feed('<h1>Peoria Flock Safety ALPR cameras</h1>'
        '<a href="'+URL+'">Flock cameras GIS</a>')
 return p
class OfficialExternal(unittest.TestCase):
 def test_exact_government_parent_and_public_layer_required(self):
  with patch.object(v,"api_request",side_effect=[[LINK],[CANDIDATE],[SOURCE],[ROOT]]):
   actual=list(v.source_inputs())
  self.assertEqual(len(actual),1)
  with patch.object(v,"api_request",side_effect=[
    [{**LINK,"disclosure_url":"https://other.example.gov/map"}],
    [CANDIDATE],[SOURCE],[ROOT]]):
   self.assertEqual(list(v.source_inputs()),[])
 def test_esri_org_is_independently_checked(self):
  response={"results":[{"type":"Feature Service","url":URL.rsplit("/",1)[0],
                       "owner":"PeoriaData","orgId":ORGID}]}
  portal={"id":ORGID,"name":"City of Peoria GIS"}
  with patch.object(v,"get_official_json",side_effect=[response,portal]):
   self.assertEqual(v.arcgis_original_org(URL.rsplit("/",1)[0],"Peoria, AZ"),
                    (ORGID,"City of Peoria GIS"))
  with patch.object(v,"get_official_json",side_effect=[response,
      {"id":ORGID,"name":"Community Map Volunteers"}]):
   with self.assertRaises(ValueError):
    v.arcgis_original_org(URL.rsplit("/",1)[0],"Peoria, AZ")
 def test_metadata_point_only_and_live_original_government_link(self):
  with (patch.object(v,"fetch_government_page",return_value=(doc(),'a'*64)),
        patch.object(v,"arcgis_original_org",return_value=(ORGID,"City of Peoria GIS")),
        patch.object(v,"get_official_json",side_effect=[SERVICE,LAYER,POINTS])):
   result=v.source_payload(SOURCE,ROOT,LINK,CANDIDATE)
  self.assertEqual(result["p_locations"],[{"id":7,"lat":33.6,"lon":-112.2}])
  self.assertEqual(result["p_org_id"],ORGID)
  with (patch.object(v,"fetch_government_page",return_value=(doc(),'b'*64)),
        patch.object(v,"arcgis_original_org") as org):
   with self.assertRaises(ValueError):
    v.source_payload(SOURCE,ROOT,LINK,CANDIDATE)
  org.assert_not_called()
 def test_service_root_government_link_keeps_exact_layer_binding(self):
  service=URL.rsplit("/",1)[0]
  p=Anchors()
  p.feed('<h1>Peoria Flock Safety ALPR camera program</h1>'
         '<a href="'+service+'">Flock camera GIS service</a>')
  link={**LINK,"discovery_method":"government_page_direct_service_v1"}
  with (patch.object(v,"fetch_government_page",return_value=(p,'a'*64)),
        patch.object(v,"arcgis_original_org",return_value=(ORGID,"City of Peoria GIS")),
        patch.object(v,"get_official_json",side_effect=[SERVICE,LAYER,POINTS])):
   result=v.source_payload(SOURCE,ROOT,link,CANDIDATE)
  self.assertEqual(result["p_gis_layer_url"],URL)
  self.assertEqual(len(result["p_locations"]),1)
  with patch.object(v,"api_request",side_effect=[[link],[CANDIDATE],[SOURCE],[ROOT]]):
   self.assertEqual(len(list(v.source_inputs())),1)
 def test_service_directory_only_qualifies_when_entire_catalog_has_one_flock_layer(self):
  service=URL.rsplit("/",1)[0]
  v.verify_service_directory_endorsement(
    {"layers":[{"id":0,"name":"Flock Cameras"}]},URL,"Flock Cameras",
    "government_page_direct_service_v1")
  for listing in (
    {"layers":[{"id":0,"name":"Flock Cameras"},{"id":1,"name":"Flock Cameras - Annex"}]},
    {"layers":[{"id":1,"name":"Flock Cameras"}]},
    {"layers":[]},
    {"layers":[{"id":0,"name":"Traffic Cameras"}]},
  ):
   with self.assertRaises(ValueError):
    v.verify_service_directory_endorsement(
      listing,URL,"Flock Cameras","government_page_direct_service_v1")
 def test_direct_exact_layer_does_not_infer_government_ownership(self):
  # Exact direct-layer endorsement has different provenance from service
  # root matching, and still requires all remaining parent, schema, org
  # and duplicate-camera gates.
  v.verify_service_directory_endorsement({},URL,"Flock Cameras",
     "government_page_direct_anchor_v1")
 def test_unbound_service_link_cannot_approve_layer(self):
  p=Anchors()
  p.feed('<h1>Peoria Flock cameras</h1><a href="https://example.com/irrelevant">Maps</a>')
  link={**LINK,"discovery_method":"government_page_direct_service_v1"}
  with (patch.object(v,"fetch_government_page",return_value=(p,'a'*64)),
        patch.object(v,"arcgis_original_org") as org):
   with self.assertRaises(ValueError):
    v.source_payload(SOURCE,ROOT,link,CANDIDATE)
  org.assert_not_called()
 def test_no_unreviewed_promotions_on_dry_run(self):
  with (patch.object(v,"source_inputs",return_value=[(SOURCE,ROOT,LINK,CANDIDATE)]),
        patch.object(v,"source_payload",return_value={"p_locations":[{"id":7}]}),
        patch.object(v,"api_request") as api):
   self.assertEqual(v.run(True)["registered"],0)
  api.assert_not_called()
 def test_third_party_layer_without_original_government_link_never_eligible(self):
  with patch.object(v,"api_request",side_effect=[[],[CANDIDATE],[SOURCE],[ROOT]]):
   self.assertEqual(list(v.source_inputs()),[])
if __name__=="__main__":unittest.main()
