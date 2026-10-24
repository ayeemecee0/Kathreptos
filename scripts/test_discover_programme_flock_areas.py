import unittest
from unittest.mock import patch
from discover_government_gis_links import Anchors
import discover_programme_flock_areas as d

PROGRAM={'program_key':'city_example_xx','jurisdiction_label':'City Example, XX',
         'official_evidence_url':'https://city.example.gov/public-safety/flock'}
PAGE=PROGRAM['official_evidence_url']
LAYER='https://gis.city.example.gov/arcgis/rest/services/Police/Flock/MapServer/3'
RING=[[-104.8,38.8],[-104.7,38.8],[-104.7,38.9],[-104.8,38.8]]
def html(txt):
 h=Anchors();h.feed(txt);return h
class IndependentProgrammes(unittest.TestCase):
 def test_gov_programme_direct_link_without_camera_point_authority(self):
  h=html('<h1>Flock Safety ALPR cameras</h1><a href="'+LAYER+'">Government GIS map</a>')
  self.assertEqual(d.direct_government_polygon_links(PAGE,h),[LAYER])
  self.assertEqual(d.direct_government_polygon_links(
    PAGE,html('<h1>Police GIS service</h1><a href="'+LAYER+'">Camera map</a>')),[])
 def test_wrong_host_and_private_map_urls_rejected(self):
  h=html('<h1>Flock Safety cameras</h1>'
         '<a href="https://other.gov/police/flock/MapServer/1">GIS camera map</a>'
         '<a href="http://gis.city.example.gov/arcgis/rest/services/Police/Flock/MapServer/3">GIS</a>')
  self.assertEqual(d.direct_government_polygon_links(PAGE,h),[])
 def test_original_polygon_only_not_city_centroid_circle(self):
  metadata={'name':'Flock Deployment Areas','type':'Feature Layer',
   'geometryType':'esriGeometryPolygon','objectIdField':'OBJECTID',
   'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'}]}
  ids={'objectIds':[2]}
  features={'features':[{'attributes':{'OBJECTID':2},'geometry':{'rings':[RING]}}]}
  with patch.object(d,'government_gis_json',side_effect=[metadata,ids,features,ids]):
   result=d.original_polygon_payloads(PROGRAM,LAYER,'a'*64)
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]['p_outline'],RING)
  self.assertEqual(result[0]['p_program_key'],PROGRAM['program_key'])
 def test_generic_traffic_polygon_and_multipart_polygon_held(self):
  for meta,features in (
    ({'name':'City Boundary','type':'Feature Layer','geometryType':'esriGeometryPolygon',
       'objectIdField':'OBJECTID','fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'}]},
      {'features':[{'attributes':{'OBJECTID':2},'geometry':{'rings':[RING]}}]}),
    ({'name':'Flock Deployment Areas','type':'Feature Layer','geometryType':'esriGeometryPolygon',
       'objectIdField':'OBJECTID','fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'}]},
      {'features':[{'attributes':{'OBJECTID':2},'geometry':{'rings':[RING,RING]}}]})
  ):
   with patch.object(d,'government_gis_json',side_effect=[
      meta,{'objectIds':[2]},features,{'objectIds':[2]}]):
    with self.assertRaises(ValueError):
     d.original_polygon_payloads(PROGRAM,LAYER,'a'*64)
 def test_changed_original_government_page_withdraws_removed_link(self):
  record={'area_key':'area_original_test_001',
    'government_program_key':PROGRAM['program_key'],
    'evidence_url':LAYER,'government_page_sha256':'a'*64}
  updated=html('<h1>Flock Safety ALPR camera programme updated</h1>'
               '<p>The previous official GIS polygon link was removed.</p>')
  with (patch.object(d,'government_programmes',return_value=[PROGRAM]),
        patch.object(d,'existing_programme_areas',
          return_value={PROGRAM['program_key']:[record]}),
        patch.object(d,'fetch_government_page',return_value=(updated,'b'*64)),
        patch.object(d,'api_request',return_value=True) as rpc):
   result=d.run(dry_run=False)
  self.assertEqual(result['withdrawn_original_link_lost'],1)
  self.assertEqual(rpc.call_args.args[0],
                   'rpc/withdraw_programme_area_after_link_loss')
  self.assertEqual(rpc.call_args.kwargs['payload']['p_area_key'],
                   record['area_key'])
 def test_unchanged_original_page_cannot_withdraw_and_failed_pages_hold(self):
  record={'area_key':'area_original_test_001',
    'government_program_key':PROGRAM['program_key'],
    'evidence_url':LAYER,'government_page_sha256':'a'*64}
  page=html('<h1>Flock cameras and GIS links temporarily missing</h1>')
  with (patch.object(d,'government_programmes',return_value=[PROGRAM]),
        patch.object(d,'existing_programme_areas',
          return_value={PROGRAM['program_key']:[record]}),
        patch.object(d,'fetch_government_page',return_value=(page,'a'*64)),
        patch.object(d,'api_request') as rpc):
   result=d.run()
  self.assertEqual(result['unchanged_missing_link_held'],1)
  rpc.assert_not_called()
 def test_unreachable_government_site_does_not_revoke_any_area(self):
  record={'area_key':'area_original_test_001',
    'government_program_key':PROGRAM['program_key'],
    'evidence_url':LAYER,'government_page_sha256':'a'*64}
  with (patch.object(d,'government_programmes',return_value=[PROGRAM]),
        patch.object(d,'existing_programme_areas',
          return_value={PROGRAM['program_key']:[record]}),
        patch.object(d,'fetch_government_page',
          side_effect=RuntimeError('site inaccessible')),
        patch.object(d,'api_request') as rpc):
   with self.assertRaises(RuntimeError):
    d.run()
  rpc.assert_not_called()
 def test_dryrun_never_writes_any_map_geometry(self):
  h=html('<h1>Flock Safety ALPR cameras</h1><a href="'+LAYER+'">GIS map</a>')
  with (patch.object(d,'government_programmes',return_value=[PROGRAM]),
        patch.object(d,'existing_programme_areas',return_value={}),
        patch.object(d,'fetch_government_page',return_value=(h,'a'*64)),
        patch.object(d,'original_polygon_payloads',return_value=[{'p_area_key':'area_test'}]),
        patch.object(d,'api_request') as api):
   result=d.run(dry_run=True)
  self.assertEqual(result['verified_original_polygon_features'],1)
  api.assert_not_called()
if __name__=='__main__':unittest.main()
