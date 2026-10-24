import contextlib
import io
import unittest
from unittest.mock import patch
from discover_government_gis_links import Anchors
import probe_original_gov_arcgis_org_links as a

ORG={'org_id':'ABCD12345678','portal_url_key':'CityGIS',
     'portal_base_url':'maps.arcgis.com'}
URL='https://services3.arcgis.com/0Uo0Kvp9YTHRegvR/arcgis/rest/services/Flock_Cameras_-_Public/FeatureServer/0'
C={'gis_layer_url':URL,'layer_name':'Flock Cameras'}

def document(html):
    p=Anchors()
    p.feed(html)
    return p

class GovPublisher(unittest.TestCase):
 def test_exact_esri_organization_link_not_generic_esri_page(self):
    self.assertTrue(a.is_exact_esri_org_link(
        'https://www.arcgis.com/home/organization.html?orgId=ABCD12345678',ORG))
    self.assertTrue(a.is_exact_esri_org_link('https://citygis.maps.arcgis.com/home/index.html',ORG))
    for u in ('https://www.arcgis.com/home/organization.html?orgId=anotherOrgId',
              'https://www.arcgis.com/home/organization.html',
              'https://www.arcgis.com/home/organization.html?orgId=ABCD12345678&orgId=other',
              'https://www.arcgis.com/home/item.html?id=ABCD12345678',
              'https://evil.example/organization.html?orgId=ABCD12345678',
              'http://www.arcgis.com/home/organization.html?orgId=ABCD12345678',
              'https://citygis.maps.arcgis.com/home/index.html?redirect=evil',
              'https://fake.maps.arcgis.com/home/index.html'):
       with self.subTest(url=u):
        self.assertFalse(a.is_exact_esri_org_link(u,ORG))
 def test_false_esri_portal_custom_domain_never_authorized(self):
    self.assertFalse(a.is_exact_esri_org_link(
      'https://citygis.maps.arcgis.com/home/index.html',
      {**ORG,'portal_base_url':'attacker.example.com'}))
 def test_original_agency_link_must_match_exact_org(self):
    original=document('<a href="https://citygis.maps.arcgis.com/home/">City GIS</a>')
    self.assertTrue(a.linked_government_org(original,'https://originalcity.gov/gis',ORG))
    original=document('<a href="https://www.arcgis.com/">Generic Esri</a>')
    self.assertFalse(a.linked_government_org(original,'https://originalcity.gov/gis',ORG))
 def test_readonly_audit_does_not_promote_from_portal_claim(self):
    docs=document('<a href="https://citygis.maps.arcgis.com/home/">City GIS</a>')
    fake='https://originalcity.gov/gis'
    with (patch.object(a,'candidate_inputs',return_value=([C],[],[])),
          patch.object(a,'government_pages',return_value=[fake]),
          patch.object(a,'fetch_government_page',return_value=(docs,'a'*64)),
          patch.object(a,'check_external',return_value=
            'verified_arcgis_metadata_only_missing_original_government_link'),
          patch.object(a,'inspect_arcgis_publisher',return_value=ORG),
          io.StringIO() as output):
      with contextlib.redirect_stdout(output):
       result=a.run()
      logs=output.getvalue()
    self.assertEqual(result['gov_page_links_exact_esri_organization'],1)
    self.assertIn('camera locations automatically verified: 0',logs)
    self.assertNotIn(URL,logs)
    self.assertNotIn(fake,logs)
 def test_missing_gov_endorsement_held(self):
    docs=document('<a href="https://unverified.maps.arcgis.com/home/">Map</a>')
    with (patch.object(a,'candidate_inputs',return_value=([C],[],[])),
          patch.object(a,'government_pages',return_value=['https://city.gov/gis']),
          patch.object(a,'fetch_government_page',return_value=(docs,'a'*64)),
          patch.object(a,'check_external',return_value=
           'verified_arcgis_metadata_only_missing_original_government_link'),
          patch.object(a,'inspect_arcgis_publisher',return_value=ORG),
          io.StringIO() as output):
      with contextlib.redirect_stdout(output):
       result=a.run()
    self.assertEqual(result['original_government_organization_link_missing'],1)
    self.assertEqual(result['gov_page_links_exact_esri_organization'],0)
 def test_unknown_original_gov_page_fails_closed(self):
    with (patch.object(a,'candidate_inputs',return_value=([C],[],[])),
          patch.object(a,'government_pages',return_value=[])):
      with self.assertRaisesRegex(ValueError,'No independently governed'):
       a.run()

if __name__=='__main__':unittest.main()
