import unittest
from unittest.mock import patch
from discover_government_gis_links import Anchors
import audit_agency_hosted_gis as a

SOURCE=a.SOURCES[0]
def document():
 p=Anchors()
 p.feed('<h1>Alachua County Geographic Information Systems</h1>'
        '<a href="https://mapgenius.alachuacounty.us/">Map Genius</a>')
 return p
LAYER={'name':'Flock Cameras','geometryType':'esriGeometryPoint',
       'type':'Feature Layer','objectIdField':'OBJECTID',
       'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'},
                 {'name':'CameraID','type':'esriFieldTypeString'}]}
SERVICE={'layers':[{'id':0,'name':'Flock Cameras'}]}
IDS={'objectIds':[2,7]}
FEATURES={'features':[
 {'attributes':{'OBJECTID':2,'CameraID':'Unit 2'},
  'geometry':{'x':-82.3,'y':29.6}},
 {'attributes':{'OBJECTID':7,'CameraID':'Unit 7'},
  'geometry':{'x':-82.35,'y':29.65}},
]}
def normal():
 return [SERVICE,LAYER,IDS,FEATURES]

class AgencyPath(unittest.TestCase):
 def test_host_control_via_original_agency_page_not_exact_layer_backlink(self):
  self.assertEqual(a.authority(SOURCE,document()),'alachuacounty.us')
  p=Anchors();p.feed('<a href="https://maps.example.com/">GIS</a>')
  with self.assertRaisesRegex(ValueError,'does not link'):
   a.authority(SOURCE,p)
 def test_bogus_external_service_cannot_inherit_government_authentication(self):
  src={**SOURCE,'layer':'https://services.arcgis.com/Evil/arcgis/rest/services/Flock/FeatureServer/0'}
  with self.assertRaisesRegex(ValueError,'original-agency'):
   a.authority(src,document())
 def test_complete_original_agency_identity_and_geometry(self):
  with (patch.object(a,'public_dns',return_value=True),
        patch.object(a,'fetch_government_page',return_value=(document(),'a'*64)),
        patch.object(a,'get_official_json',side_effect=normal())):
   out=a.inspect(SOURCE)
  self.assertEqual(out['point_count'],2)
  self.assertEqual(out['individual_id_field'],'CameraID')
  self.assertEqual(out['status'],'agency_host_identity_and_complete_layer_geometry_checked')
  self.assertNotIn('points',out)
 def test_first_party_source_objectid_only_is_sufficient_feature_identity(self):
  original={**LAYER,'fields':LAYER['fields'][:1]}
  original_features={'features':[
   {'attributes':{'OBJECTID':2},'geometry':{'x':-82.3,'y':29.6}},
   {'attributes':{'OBJECTID':7},'geometry':{'x':-82.35,'y':29.65}},
  ]}
  with (patch.object(a,'public_dns',return_value=True),
        patch.object(a,'fetch_government_page',return_value=(document(),'a'*64)),
        patch.object(a,'get_official_json',side_effect=[SERVICE,original,IDS,original_features])):
   out=a.inspect(SOURCE)
  self.assertEqual(out['individual_id_field'],'OBJECTID')
  self.assertEqual(out['identifier_basis'],'arcgis_typed_objectid')
  self.assertEqual(out['point_count'],2)
 def test_rejects_partial_or_wrong_camera_inventories(self):
  variations=[
   [SERVICE,{**LAYER,'geometryType':'esriGeometryPolygon'},IDS,FEATURES],
   [SERVICE,{**LAYER,'name':'Traffic Cameras'},IDS,FEATURES],
   [SERVICE,{**LAYER,'fields':[{'name':'CameraID','type':'esriFieldTypeString'}]},IDS,FEATURES],
   [SERVICE,LAYER,IDS,{'features':FEATURES['features'][:1]}],
   [SERVICE,LAYER,IDS,{'features':[FEATURES['features'][0]]*2}],
   [SERVICE,LAYER,IDS,{'features':[
     {**FEATURES['features'][0],'geometry':{'x':-82.3,'y':51}},
     FEATURES['features'][1]]}],
  ]
  for items in variations:
   with self.subTest(fixture=str(items)[:60]):
    with (patch.object(a,'public_dns',return_value=True),
          patch.object(a,'fetch_government_page',return_value=(document(),'a'*64)),
          patch.object(a,'get_official_json',side_effect=items)):
     with self.assertRaises(ValueError):a.inspect(SOURCE)
 def test_dry_run_does_not_touch_private_or_public_database(self):
  with (patch.object(a,'inspect',return_value={
      'point_count':2,'layer_url':SOURCE['layer'],'layer_name':'Flock Cameras',
      'object_id_field':'OBJECTID'
    }), patch.object(a,'stage_candidate') as stage):
   result=a.run(dry_run=True)
  self.assertEqual(result['qualified_original_agency_layers'],1)
  stage.assert_not_called()
 def test_private_stage_does_not_touch_camera_publications(self):
  with (patch.object(a,'inspect',return_value={
      'point_count':2,'layer_url':SOURCE['layer'],'layer_name':'Flock Cameras',
      'object_id_field':'OBJECTID'
    }),patch.object(a,'stage_candidate') as stage):
   result=a.run(dry_run=False)
  self.assertEqual(result['private_sources_staged'],1)
  staged=stage.call_args.args[0]
  self.assertEqual(staged['trust_status'],'unverified')
  self.assertEqual(staged['gis_layer_url'],SOURCE['layer'])
  self.assertNotIn('latitude',staged)
  self.assertNotIn('longitude',staged)
 def test_only_pinned_source_may_be_fetched(self):
  with patch.object(a,'fetch_government_page') as network:
   with self.assertRaisesRegex(ValueError,'pinned'):a.inspect(
       {**SOURCE,'layer':'https://maps.alachuacounty.us/other/FeatureServer/0'})
  network.assert_not_called()

if __name__=='__main__':unittest.main()
