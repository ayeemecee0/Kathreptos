"""Government-site GIS link verification must not infer camera authority."""
import unittest
from unittest.mock import patch
import discover_government_gis_links as d

PAGE='https://city.example.gov/police/flock'
HTML="""<html><h1>Flock Safety ALPR program</h1>
<a href="https://gis.city.example.gov/arcgis/rest/services/Flock/MapServer/4">Flock camera GIS locations</a>
<a href="https://evil.example/MapServer/8">Other</a>
<a href="/police/flock-map">View camera map</a>
</html>"""
class GovernmentCrawler(unittest.TestCase):
 def document(self,markup):
  p=d.Anchors();p.feed(markup);return p
 def test_original_disclosure_creates_private_link_with_sha(self):
  p=self.document(HTML)
  rows=d.gis_candidate_links(p,PAGE,'city.example.gov',
    'government_page_direct_anchor_v1','City Example, ST','a'*64)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]['government_page_sha256'],'a'*64)
  self.assertIn('gis.city.example.gov',rows[0]['gis_layer_url'])
  self.assertEqual(rows[0]['discovery_method'],'government_page_direct_anchor_v1')
 def test_never_trust_a_search_result_or_vendor_only_map(self):
  self.assertFalse(d.gis_candidate_links(self.document(
    '<a href="https://gis.city.example.gov/foo/FeatureServer/0">Flock cameras</a>'),
    PAGE,'city.example.gov','government_page_direct_anchor_v1','City Example, ST','b'*64))
 def test_plain_flock_cameras_government_prose_is_eligible_for_private_lead(self):
  page=self.document('<h1>City police Flock cameras</h1>'
      '<p>Our license plate readers are used for public safety.</p>'
      '<a href="https://gis.city.example.gov/a/MapServer/3">Flock GIS camera map</a>')
  rows=d.gis_candidate_links(page,PAGE,'city.example.gov',
      'government_page_direct_anchor_v1','City Example, ST','a'*64)
  self.assertEqual(len(rows),1)
  self.assertTrue(d.original_camera_disclosure(page))
 def test_link_text_only_is_not_original_flock_program_evidence(self):
  doc=self.document('<h2>General municipal GIS links</h2>'
       '<a href="https://gis.city.example.gov/a/MapServer/3">Flock cameras</a>')
  self.assertFalse(d.original_camera_disclosure(doc))
  self.assertEqual(d.gis_candidate_links(doc,PAGE,'city.example.gov',
      'government_page_direct_anchor_v1','City Example, ST','a'*64),[])
 def test_external_and_javascript_pages_not_followed(self):
  p=self.document(HTML+'<a href="javascript:alert(1)">Flock GIS map</a>')
  pages=d.same_site_page_links(p,PAGE,'city.example.gov')
  self.assertEqual(pages,['https://city.example.gov/police/flock-map'])
 def test_offsite_redirect_is_blocked(self):
  with patch.object(d,'public_dns',return_value=False):
   with self.assertRaises(ValueError): d.fetch_government_page(PAGE)
 def test_queue_never_grants_source_trust(self):
  row=d.gis_candidate_links(self.document(HTML),PAGE,'city.example.gov',
    'government_page_direct_anchor_v1','City Example, ST','a'*64)[0]
  with patch.object(d,'api_request',return_value=None) as api:
   d.stage([row])
  self.assertIn('government_gis_disclosure_leads',api.call_args.args[0])
  self.assertNotIn('trusted_flock_gis_sources',api.call_args.args[0])
 def test_same_gov_original_camera_link_reaches_restricted_verification_queue(self):
  document=self.document(HTML)
  with (patch.object(d,'load_approved_domains',return_value={}),
        patch.object(d,'get_seed_pages',return_value=([(PAGE,'Example, ST')],{PAGE})),
        patch.object(d,'fetch_government_page',return_value=(document,'a'*64)),
        patch.object(d,'same_site_page_links',return_value=[]),
        patch.object(d,'stage') as stage_leads,
        patch.object(d,'stage_same_gov_flock_page') as queue):
   result=d.scan(dry_run=False)
  self.assertEqual(result['original_gov_pages_queued'],1)
  stage_leads.assert_called_once()
  queued=queue.call_args.args[0]
  self.assertEqual(queued['page_sha256'],'a'*64)
  self.assertEqual(queued['gis_links'],[
    'https://gis.city.example.gov/arcgis/rest/services/Flock/MapServer/4'])
  self.assertNotIn('trusted_flock_gis_sources',str(queued))
 def test_third_party_esri_disclosure_stays_out_of_autoqueue(self):
  external=self.document('<h1>Flock Safety ALPR cameras</h1>'
      '<a href="https://services.arcgis.com/Example/arcgis/rest/services/Flock/FeatureServer/4">'
      'Flock GIS cameras</a>')
  with (patch.object(d,'load_approved_domains',return_value={}),
        patch.object(d,'get_seed_pages',return_value=([(PAGE,'Example, ST')],{PAGE})),
        patch.object(d,'fetch_government_page',return_value=(external,'b'*64)),
        patch.object(d,'stage') as stage_leads,
        patch.object(d,'stage_same_gov_flock_page') as queue):
   result=d.scan(dry_run=False)
  self.assertEqual(result['original_gov_pages_queued'],0)
  stage_leads.assert_called_once()
  queue.assert_not_called()
 def test_unverified_custom_domain_not_approved(self):
  a={'example.com':{'domain':'example.com','allow_www':False}}
  self.assertIsNone(d.normalized_url('http://example.com/page'))
  self.assertIsNone(d.normalized_url('https://example.com/page#fragment'))
  self.assertIsNotNone(d.normalized_url('https://example.com/page'))
if __name__=='__main__':unittest.main()
