"""Non-network tests for the alternate original government -> ArcGIS item link path."""
import unittest
from unittest.mock import patch
from discover_government_gis_links import Anchors
import discover_gov_esri_publisher_links as m

SERVICE='https://services3.arcgis.com/0Uo0Kvp9YTHRegvR/arcgis/rest/services/Flock_Cameras_-_Public/FeatureServer/0'
ITEM_ID='a'*32
OWNER='GovData'
ORG={'org_id':'ABCD12345678','owner':OWNER,
     'portal_url_key':'CityGIS','portal_base_url':'maps.arcgis.com',
     'original_service_item_id':ITEM_ID}
GOV='https://records.examplecity.gov/police/alpr'

def doc(href,flock=True):
    obj=Anchors()
    obj.feed('<p>'+('Flock Safety ALPR cameras' if flock else 'Maps')+
             '</p><a href="'+href+'">GIS resource</a>')
    return obj

class OriginalItem(unittest.TestCase):
 def test_original_item_service_and_owner_must_match(self):
    service=SERVICE.rsplit('/',1)[0]
    index={'results':[{'id':ITEM_ID,'url':service,
                      'type':'Feature Service','owner':OWNER}]}
    details={'id':ITEM_ID,'url':service,
             'type':'Feature Service','owner':OWNER}
    seen=[]
    def read(u):
       seen.append(u)
       return index if '/search?' in u else details
    self.assertEqual(m.inspect_original_service_item(SERVICE,OWNER,read),ITEM_ID)
    self.assertEqual(len(seen),2)
    self.assertTrue(seen[1].startswith('https://www.arcgis.com/sharing/rest/content/items/'))
    self.assertIsNone(m.inspect_original_service_item(SERVICE,OWNER,
        lambda u: index if '/search?' in u else {**details,'owner':'Other'}))
    self.assertIsNone(m.inspect_original_service_item(SERVICE,OWNER,
        lambda u: index if '/search?' in u else {**details,'url':'https://evil.example/FeatureServer'}))
 def test_unknown_host_does_not_make_an_esri_item_authoritative(self):
    fake='https://other.example.com/public/Flock/FeatureServer/0'
    self.assertIsNone(m.inspect_original_service_item(fake,OWNER,
      lambda u: (_ for _ in ()).throw(AssertionError('Do not fetch arbitrary host'))))
 def test_original_government_exact_item_anchor(self):
    good='https://www.arcgis.com/home/item.html?id='+ITEM_ID
    self.assertTrue(m.linked_original_esri_service_item(doc(good),GOV,ORG))
    self.assertEqual(m.evaluate_page({},ORG,GOV,doc(good)),
                     'agency_page_links_exact_esri_feature_service_item_and_mentions_flock')
    self.assertEqual(m.evaluate_page({},ORG,GOV,doc(good,False)),
                     'agency_page_links_exact_esri_feature_service_item_only_no_flock_evidence')
    self.assertEqual(len(m.queries_for_identity(ORG)),3)
 def test_wrong_link_never_qualifies_as_exact_item(self):
    for url in (
       'https://www.arcgis.com/home/item.html?id='+('b'*32),
       'https://www.arcgis.com/home/item.html?id='+ITEM_ID+'&id='+('b'*32),
       'https://fake.arcgis.com/home/item.html?id='+ITEM_ID,
       'http://www.arcgis.com/home/item.html?id='+ITEM_ID,
       'https://www.arcgis.com/home/item.html?id='+ITEM_ID+'#fake',
       'https://www.arcgis.com/home/item.html?id='+ITEM_ID+'&redirect=https://evil.example',
    ):
       with self.subTest(url=url):
          self.assertFalse(m.linked_original_esri_service_item(doc(url),GOV,ORG))
 def test_branded_portal_requires_same_independently_checked_esri_org(self):
    good='https://citygis.maps.arcgis.com/home/item.html?id='+ITEM_ID
    self.assertTrue(m.linked_original_esri_service_item(doc(good),GOV,ORG))
    self.assertFalse(m.linked_original_esri_service_item(
       doc(good),GOV,{**ORG,'portal_url_key':'AnotherCity'}))
    self.assertFalse(m.linked_original_esri_service_item(
       doc(good),GOV,{**ORG,'portal_base_url':'malicious.example'}))

if __name__=='__main__':unittest.main()
