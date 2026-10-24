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
 def test_gov_page_stages_direct_gis_service_root_without_inventing_layer(self):
  page="https://city.example.gov/flock"
  service="https://gis.city.example.gov/arcgis/rest/services/PublicSafety/MapServer"
  doc=html('<h2>Flock Safety ALPR cameras</h2>'
           '<a href="'+service+'">Flock GIS camera map</a>')
  record=d.page_candidate(page,"CA","city Flock cameras",doc,'a'*64)
  self.assertEqual(record["gis_links"],[service])
 def test_generic_traffic_service_root_not_staged_as_flock_source(self):
  page="https://city.example.gov/flock"
  service="https://gis.city.example.gov/arcgis/rest/services/Traffic/MapServer"
  doc=html('<h2>Flock Safety ALPR cameras</h2>'
           '<a href="'+service+'">General data</a>')
  self.assertEqual(d.page_candidate(page,"CA","city Flock cameras",doc,'a'*64)["gis_links"],[])
 def test_revisited_original_government_links_update_not_ignore(self):
  page="https://city.example.gov/flock"
  item={"page_url":page,"page_sha256":'b'*64,
        "gis_links":["https://gis.city.example.gov/x/MapServer/3"]}
  with patch.object(d,"api_request",side_effect=[
      [{"page_sha256":'a'*64,"gis_links":[]}],True
  ]) as api:
   d.stage(item)
  self.assertEqual(api.call_count,2)
  self.assertIn("rpc/refresh_original_government_gis_search_lead",api.call_args.args[0])
  self.assertEqual(api.call_args.kwargs["payload"]["p_expected_previous_sha"],'a'*64)
  self.assertEqual(api.call_args.kwargs["payload"]["p_gis_links"],item["gis_links"])
 def test_government_subpage_crawl_preserves_independent_page_digest(self):
  root="https://city.example.gov/flock"
  sub="https://city.example.gov/public-safety/flock-map"
  layer="https://gis.city.example.gov/arcgis/rest/services/Police/Flock/MapServer/7"
  parent=html('<h1>Flock Safety ALPR cameras</h1>'+
      '<a href="/public-safety/flock-map">Flock GIS map</a>')
  child=html('<h2>Flock Safety ALPR cameras in city</h2>'+
      '<a href="'+layer+'">Flock camera GIS</a>')
  self.assertEqual(d.direct_same_host_flock_pages(parent,root),[sub])
  with (patch.object(d,"search_provider",return_value=("bing-rss",[root])),
        patch.object(d,"upstream_government_source_seeds",return_value={}),
        patch.object(d,"previously_checked_original_pages",return_value=set()),
        patch.object(d,"public_dns",return_value=True),
        patch.object(d,"fetch_government_page",side_effect=[(parent,'a'*64),(child,'b'*64)]),
        patch.object(d,"stage") as stage):
   result=d.scan(False,[("TX","Flock cameras original city.gov")])
  self.assertEqual(result["secondary_pages_with_direct_gis"],1)
  self.assertEqual(stage.call_count,2)
  staged=stage.call_args.args[0]
  self.assertEqual(staged["page_url"],sub)
  self.assertEqual(staged["page_sha256"],'b'*64)
  self.assertEqual(staged["gis_links"],[layer])
 def test_no_outside_host_or_source_less_subpage_promotion(self):
  root="https://city.example.gov/flock"
  parent=html('<h1>Flock Safety ALPR cameras</h1>'+
    '<a href="https://other.example.gov/maps">Flock map</a>'+
    '<a href="/flock-second">Flock GIS</a>')
  self.assertEqual(d.direct_same_host_flock_pages(parent,root),
                   ["https://city.example.gov/flock-second"])
  child=html('<h2>Generic municipal traffic map</h2>'+
    '<a href="https://gis.city.example.gov/a/MapServer/3">Camera GIS</a>')
  self.assertIsNone(d.page_candidate("https://city.example.gov/flock-second",
      "TX","Independent government evidence",child,'b'*64))
 def test_unverified_only_and_no_public_write(self):
  with patch.object(d,"api_request",side_effect=[[],None]) as api:
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
 def test_unvisited_government_pages_are_sampled_before_old_sources(self):
  import datetime as dt
  hits={f"https://city{i}.example.gov/flock":("State","original source")
        for i in range(80)}
  old=set(list(hits)[:65])
  ordered=d.prioritize_new_government_pages(hits,old,
    dt.date(2026,10,23))
  self.assertEqual(len(ordered),80)
  self.assertTrue(all(item[0] not in old for item in ordered[:15]))
  self.assertTrue(all(item[0] in old for item in ordered[15:]))
 def test_page_priority_rotates_daily_deterministically(self):
  import datetime as dt
  hits={f"https://city{i}.example.gov/flock":("State","source")
        for i in range(75)}
  today=d.prioritize_new_government_pages(hits,set(),dt.date(2026,10,23))
  tomorrow=d.prioritize_new_government_pages(hits,set(),dt.date(2026,10,24))
  self.assertNotEqual([x[0] for x in today],[x[0] for x in tomorrow])
  self.assertEqual(today,
    d.prioritize_new_government_pages(hits,set(),dt.date(2026,10,23)))
 def test_no_mutation_dryrun(self):
  h=html('<h2>Flock Safety ALPR cameras</h2>')
  with (patch.object(d,"search_provider",return_value=("bing-rss",["https://city.example.gov/flock"])),
        patch.object(d,"upstream_government_source_seeds",return_value={}),
        patch.object(d,"previously_checked_original_pages",return_value=set()),
        patch.object(d,"public_dns",return_value=True),
        patch.object(d,"fetch_government_page",return_value=(h,'a'*64)),
        patch.object(d,"stage") as stage):
   result=d.scan(True,[("National",'Flock Safety GIS site:gov')])
  self.assertEqual(result["pages_checked"],1)
  self.assertEqual(result["submitted"],0)
  stage.assert_not_called()
if __name__=="__main__":unittest.main()
