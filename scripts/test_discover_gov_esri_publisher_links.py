"""Offline source-first tests. No search web, Supabase call or location published."""
import contextlib
import io
import unittest
from unittest.mock import patch
from urllib.parse import quote

from discover_government_gis_links import Anchors
import discover_gov_esri_publisher_links as m

SOURCE='https://services3.arcgis.com/0Uo0Kvp9YTHRegvR/arcgis/rest/services/Flock_Cameras_-_Public/FeatureServer/0'
C={'gis_layer_url':SOURCE}
ORG={'org_id':'ABCD12345678','portal_url_key':'TownMap',
     'portal_base_url':'maps.arcgis.com'}
PAGE='https://records.examplecity.gov/police/alpr'
BAD='https://hostile.example.net/site'
def original(fl):
    page=Anchors()
    txt='Flock Safety ALPR camera deployment' if fl else 'Mapping resources'
    page.feed('<p>'+txt+'</p><a href="https://townmap.maps.arcgis.com/home/">Official GIS portal</a>')
    return page,'a'*64

class TargetedAgencyLinks(unittest.TestCase):
 def test_exact_org_identity_drives_queries_not_self_reported_city_title(self):
    self.assertEqual(m.queries_for_identity(ORG),[
      'site:.gov "orgId=ABCD12345678"',
      'site:.gov "townmap.maps.arcgis.com"'])
    self.assertEqual(m.queries_for_identity({'org_id':'!malicious'}),[])
    self.assertEqual(len(m.queries_for_identity({**ORG,'portal_url_key':'evil.example.com'})),1)
 def test_only_first_party_gov_original_search_hits(self):
    called=[]
    def search(item):
       called.append(item)
       return 'bing-rss',[BAD,PAGE,
            'http://records.examplecity.gov/police/alpr',
            'https://records.examplecity.gov/page?token=secret',
            'https://records.examplecity.gov/page#fragment',
            'https://records.examplecity.gov/news',PAGE]
    self.assertEqual(m.gov_pages(['site:.gov "orgId=ABCD12345678"'],search),
                     [PAGE,'https://records.examplecity.gov/news'])
    self.assertEqual(len(called),1)
    self.assertTrue(called[0][1].startswith('https://www.bing.com/search?'))
 def test_second_free_engine_finds_original_gov_page_when_bing_misses(self):
    searched=[]
    def search(item):
        provider,url=item
        searched.append(provider)
        if provider=='bing-rss':
            return provider,['https://unrelated.example.com/']
        if provider=='ddg-html':
            # Original government URLs returned by DDG must still pass the
            # same independent .gov and full-page link checks.
            return provider,['https://html.duckduckgo.com/l/?uddg='+quote(PAGE,safe=''),PAGE,BAD]
        raise AssertionError('Unexpected provider')
    pages=m.gov_pages(['site:.gov "orgId=ABCD12345678"'],search)
    self.assertEqual(pages,[PAGE])
    self.assertEqual(searched,['bing-rss','ddg-html'])
 def test_results_without_direct_publisher_link_cannot_be_approved(self):
    self.assertEqual(m.evaluate_page(C,ORG,PAGE,original(True)[0]),
        'agency_page_links_exact_esri_org_and_mentions_flock')
    self.assertEqual(m.evaluate_page(C,ORG,PAGE,original(False)[0]),
        'agency_page_links_exact_esri_org_only_no_flock_evidence')
    empty=Anchors()
    empty.feed('<p>Flock camera program</p><a href="https://other.maps.arcgis.com/home/">GIS</a>')
    self.assertEqual(m.evaluate_page(C,ORG,PAGE,empty),
                     'no_exact_government_to_publisher_link')
 def test_candidate_rotation_bounded_and_every_source_receives_turn(self):
    src=[{'gis_layer_url':f'https://services.arcgis.com/abc/arcgis/rest/services/Source{i}/FeatureServer/0'}
         for i in range(7)]
    for day in range(7):
       self.assertLessEqual(len(m.pick(src,day)),3)
    seen=set(x['gis_layer_url'] for day in range(7) for x in m.pick(src,day))
    self.assertEqual(len(seen),7)
    with self.assertRaisesRegex(ValueError,'budget'):
       m.pick(src*6,day=0)
 def test_full_flow_finds_exact_gov_org_lead_without_publishing(self):
    def search(item): return 'bing-rss',[PAGE]
    with (patch.object(m,'candidate_inputs',return_value=([C],[],[])),
         patch.object(m,'inspect_arcgis_publisher',return_value=ORG),
         patch.object(m,'inspect_original_service_item',return_value=None),
         patch.object(m,'fetch_government_page') as accidental,
         io.StringIO() as stdout):
       with contextlib.redirect_stdout(stdout):
          stats=m.run(search=search,fetch_page=lambda u: original(True),day=0)
       printed=stdout.getvalue()
    accidental.assert_not_called()
    self.assertEqual(stats['agency_page_links_exact_esri_org_and_mentions_flock'],1)
    self.assertIn('CAMERAS AUTOMATICALLY PUBLISHED 0',printed)
    self.assertNotIn(PAGE,printed)
    self.assertNotIn(SOURCE,printed)
    self.assertNotIn('ABCD12345678',printed)
 def test_fails_closed_when_esri_owner_unknown(self):
    with (patch.object(m,'candidate_inputs',return_value=([C],[],[])),
          patch.object(m,'inspect_arcgis_publisher',return_value='unresolved'),
          patch.object(m,'search_provider') as network):
       metrics=m.run(day=0)
    self.assertEqual(metrics['exact_arcgis_publisher_unavailable'],1)
    network.assert_not_called()
 def test_source_identity_does_not_make_esri_organization_a_government(self):
    with (patch.object(m,'candidate_inputs',return_value=([C],[],[])),
          patch.object(m,'inspect_arcgis_publisher',return_value=ORG),
          patch.object(m,'inspect_original_service_item',return_value=None)):
      metrics=m.run(search=lambda item:('bing-rss',[BAD]),
                    fetch_page=lambda u: (_ for _ in ()).throw(AssertionError('Must not fetch non-government URL')),day=0)
    self.assertEqual(metrics['government_search_results'],0)
    self.assertEqual(metrics['agency_page_links_exact_esri_org_and_mentions_flock'],0)

if __name__=='__main__':unittest.main()
