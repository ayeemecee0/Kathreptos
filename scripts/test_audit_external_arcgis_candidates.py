import unittest
from unittest.mock import patch
import audit_external_arcgis_candidates as a

LAYER="https://services3.arcgis.com/0Uo0Kvp9YTHRegvR/arcgis/rest/services/Flock_Cameras_-_Public/FeatureServer/0"
CAND={"gis_layer_url":LAYER,"layer_name":"Flock Cameras",
      "object_id_field":"OBJECTID","geometry_type":"esriGeometryPoint"}
META={"name":"Flock Cameras","type":"Feature Layer",
      "geometryType":"esriGeometryPoint","objectIdField":"OBJECTID",
      "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"}]}
SERVICE={"layers":[{"id":0,"name":"Flock Cameras"}]}

class CandidateTriage(unittest.TestCase):
 def test_arcgis_metadata_does_not_create_government_authority(self):
  with patch.object(a,'get_official_json',side_effect=[META,SERVICE]):
   self.assertEqual(a.check_external(CAND,set(),set()),
     "verified_arcgis_metadata_only_missing_original_government_link")
 def test_direct_link_still_requires_independent_attestation(self):
  with patch.object(a,'get_official_json',side_effect=[META,SERVICE]):
   self.assertEqual(a.check_external(CAND,{LAYER},set()),
     "candidate_government_link_needs_full_attestation")
 def test_mutated_metadata_is_held_even_with_government_link(self):
  with patch.object(a,'get_official_json',side_effect=[{**META,"name":"Traffic"},{"layers":[]}]):
   self.assertEqual(a.check_external(CAND,{LAYER},set()),
      "metadata_changed_or_not_point_camera_layer")
 def test_same_layer_does_not_publish_twice(self):
  with patch.object(a,'get_official_json') as get:
   self.assertEqual(a.check_external(CAND,set(),{LAYER}),
     "already_trusted_layer_review_duplicate")
   get.assert_not_called()
 def test_not_an_external_arcgis_cannot_be_auto_confirmed(self):
  with patch.object(a,'get_official_json') as get:
   self.assertEqual(a.check_external({**CAND,"gis_layer_url":"https://example.gov/a"},
                                  set(),set()),"not_external_arcgis")
   get.assert_not_called()

class ArcgisOriginalPublisher(unittest.TestCase):
 def test_exact_original_service_publisher_is_identified_not_approved(self):
  service=LAYER.rsplit('/',1)[0]
  records={'results':[{'type':'Feature Service','url':service,
                       'orgId':'abc123456789','owner':'verified_name'}]}
  portal={'id':'abc123456789','name':'City of Exampleville GIS'}
  fetches=[]
  def fetch(url):
    fetches.append(url)
    return records if '/search?' in url else portal
  outcome=a.inspect_arcgis_publisher(LAYER,fetch)
  self.assertEqual(outcome,'arcgis_org_publisher_metadata_identified_not_government_verified')
  self.assertEqual(len(fetches),2)
  self.assertIn('arcgis.com/sharing/rest/search',fetches[0])
  self.assertEqual(fetches[1],'https://www.arcgis.com/sharing/rest/portals/abc123456789?f=json')
 def test_original_item_fills_org_id_missing_from_public_search(self):
  service=LAYER.rsplit('/',1)[0]
  itemid='a'*32
  catalog={'results':[{'id':itemid,'type':'Feature Service','url':service,
                        'owner':'original_publisher'}]}
  detail={'id':itemid,'type':'Feature Service','url':service,
          'owner':'original_publisher','orgId':'abc123456789'}
  portal={'id':'abc123456789','name':'Government GIS (unverified claim)'}
  requests=[]
  def fetch(url):
    requests.append(url)
    if '/search?' in url:return catalog
    if '/content/items/' in url:return detail
    if '/portals/' in url:return portal
    self.fail('Unexpected Esri request')
  self.assertEqual(a.inspect_arcgis_publisher(LAYER,fetch),
      'arcgis_org_publisher_metadata_identified_not_government_verified')
  self.assertEqual(len(requests),3)
 def test_original_owner_profile_fallback_only_matches_exact_username(self):
  service=LAYER.rsplit('/',1)[0]
  search={'results':[{'type':'Feature Service','url':service,'owner':'publisher_user'}]}
  valid={'username':'publisher_user','orgId':'abc123456789'}
  wrong={'username':'another_person','orgId':'abc123456789'}
  def fetch(url):
    if '/search?' in url:return search
    if '/community/users/' in url:return valid
    return {'id':'abc123456789','name':'City-sounding ArcGIS group'}
  self.assertEqual(a.inspect_arcgis_publisher(LAYER,fetch),
      'arcgis_org_publisher_metadata_identified_not_government_verified')
  self.assertEqual(a.inspect_arcgis_publisher(LAYER,
      lambda url:wrong if '/community/users/' in url else fetch(url)),
      'arcgis_item_orgid_missing')
 def test_mismatched_original_item_cannot_rewrite_source_ownership(self):
  service=LAYER.rsplit('/',1)[0]
  itemid='a'*32
  search={'results':[{'id':itemid,'type':'Feature Service','url':service,
                      'owner':'original_publisher'}]}
  def fetch(url):
    if '/search?' in url:return search
    if '/content/items/' in url:return {'id':itemid,'type':'Feature Service',
       'url':'https://attacker.invalid/FeatureServer','owner':'original_publisher',
       'orgId':'abc123456789'}
    if '/community/users/' in url:return {'username':'another_user',
       'orgId':'abc123456789'}
    self.fail('Mismatched owner source must not request an Esri portal')
  self.assertEqual(a.inspect_arcgis_publisher(LAYER,fetch),
    'arcgis_item_orgid_missing')
 def test_fake_title_or_wrong_original_layer_is_never_attributed(self):
  service=LAYER.rsplit('/',1)[0]
  for catalog in ({'results':[{'type':'Feature Service','url':'https://other/FeatureServer'}]},
                  {'results':[{'type':'Feature Service','url':service}]*2},
                  {'results':[]},
                  {'results':'malformed'}):
   with self.subTest(catalog=catalog):
    self.assertEqual(a.inspect_arcgis_publisher(LAYER,lambda url:catalog),
                     'arcgis_item_not_uniquely_attributed' if isinstance(catalog['results'],list)
                     else 'unresolved_arcgis_item_search')
 def test_arcgis_org_name_is_not_independent_government_attestation(self):
  service=LAYER.rsplit('/',1)[0]
  item={'results':[{'type':'Feature Service','url':service,
                    'orgId':'abc123456789','owner':'flock_user'}]}
  for portal in ({'id':'abc123456789','name':'Official City Government GIS'},
                 {'id':'abc123456789','name':'Flock Safety Official City'},
                 {'id':'abc123456789','name':'unverified private account'}):
    with self.subTest(portal=portal):
     result=a.inspect_arcgis_publisher(
        LAYER,lambda url:item if '/search?' in url else portal)
     self.assertEqual(result,'arcgis_org_publisher_metadata_identified_not_government_verified')
 def test_malformed_owner_and_portal_are_held(self):
  service=LAYER.rsplit('/',1)[0]
  for row,outcome in [
   ({'owner':'someone'},'arcgis_item_orgid_missing'),
   ({'orgId':'abc123456789'},'arcgis_item_owner_missing')]:
   catalog={'results':[{'type':'Feature Service','url':service,**row}]}
   self.assertEqual(a.inspect_arcgis_publisher(LAYER,lambda url:catalog),outcome)
  catalog={'results':[{'type':'Feature Service','url':service,
                       'orgId':'abc123456789','owner':'someone'}]}
  self.assertEqual(a.inspect_arcgis_publisher(LAYER,lambda url:catalog
                    if '/search?' in url else {'id':'wrong','name':'Government'}),
                   'arcgis_owner_portal_unavailable')
 def test_arbitrary_hosts_not_used_for_arcgis_publisher_requests(self):
  with self.assertRaisesRegex(ValueError,'exact ArcGIS-hosted'):
   a.inspect_arcgis_publisher('https://example.gov/private/FeatureServer/0',
                             lambda url: self.fail('untrusted URL fetched'))

if __name__=="__main__":unittest.main()
