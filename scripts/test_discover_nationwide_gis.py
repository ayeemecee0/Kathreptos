import unittest
from unittest.mock import patch
from discover_government_gis_links import Anchors
import discover_nationwide_gis as d
def html(text):
 a=Anchors();a.feed(text);return a
class National(unittest.TestCase):
 def test_rotates_all_states_in_ten_daily_batches(self):
  import datetime as dt
  states=set()
  for day in range(1,11):
   plan=d.query_plan(dt.datetime(2026,1,day,tzinfo=dt.timezone.utc))
   states.update(x for x,_ in plan if x!='National')
  self.assertEqual(len(states),50)
 def test_only_original_government_urls(self):
  self.assertIsNone(d.gov_url("https://example.com/notice"))
  self.assertIsNone(d.gov_url("http://city.example.gov/notice"))
  self.assertEqual(d.gov_url("https://city.example.gov/flock"),"https://city.example.gov/flock")
 def test_requires_original_flock_camera_text(self):
  page="https://city.example.gov/flock"
  h=html('<h2>Traffic cameras</h2><a href="https://gis.example.gov/MapServer/0">GIS</a>')
  self.assertIsNone(d.page_candidate(page,"CA","Flock camera government",h,'a'*64))
  h=html('<h2>Flock Safety ALPR cameras</h2><a href="https://gis.example.gov/MapServer/0">Public map</a>')
  item=d.page_candidate(page,"CA","Flock camera government",h,'a'*64)
  self.assertEqual(item["gis_links"],["https://gis.example.gov/MapServer/0"])
  self.assertEqual(item["state_search_hint"],"CA")
 def test_unverified_only_and_no_public_write(self):
  with patch.object(d,"api_request",return_value=None) as api:
   d.stage({"page_url":"https://city.example.gov/flock"})
  self.assertIn("government_gis_search_queue",api.call_args.args[0])
  self.assertNotIn("trusted_flock_gis_sources",api.call_args.args[0])
  self.assertNotIn("flock_camera_locations",api.call_args.args[0])
 def test_paged_discovery_only_fetches_original_government_urls(self):
  with patch.object(d,"api_request",side_effect=[
     [{"url":"https://city.example.gov/flock","state_hint":"Colorado"}],
     [],[]
  ]) as api:
   d.upstream_government_source_seeds()
  self.assertIn("&url=like.*.gov/*",api.call_args_list[0].args[0])
  self.assertIn("&limit=25",api.call_args_list[0].args[0])
 def test_existing_verified_discovery_queue_expands_search(self):
  with patch.object(d,"api_request",side_effect=[
    [{"url":"https://www.city.example.gov/flock","state_hint":"Colorado"},
     {"url":"https://bad.example/alpr","state_hint":"Texas"}],
    [{"government_evidence_url":"https://city2.example.gov/flock"}],
    [{"official_evidence_url":"https://city3.example.gov/Flock","state_code":"GA"}]
  ]):
   found=d.upstream_government_source_seeds()
  self.assertEqual(len(found),3)
  self.assertNotIn("https://bad.example/alpr",found)
 def test_no_mutation_dryrun(self):
  h=html('<h2>Flock Safety ALPR cameras</h2>')
  with (patch.object(d,"search_provider",return_value=("bing-rss",["https://city.example.gov/flock"])),
        patch.object(d,"upstream_government_source_seeds",return_value={}),
        patch.object(d,"public_dns",return_value=True),
        patch.object(d,"fetch_government_page",return_value=(h,'a'*64)),
        patch.object(d,"stage") as stage):
   result=d.scan(True,[("National",'Flock Safety GIS site:gov')])
  self.assertEqual(result["pages_checked"],1)
  self.assertEqual(result["submitted"],0)
  stage.assert_not_called()
if __name__=="__main__":unittest.main()
