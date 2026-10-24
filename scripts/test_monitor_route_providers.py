import unittest
from unittest.mock import patch
import monitor_route_providers as m

CONFIG="""  geocodingServiceBase: 'https://photon.komoot.io',
  routingServiceBase: 'https://router.project-osrm.org'"""
class ProviderHealthTests(unittest.TestCase):
 def test_required_urls_are_explicit_https(self):
  c=m.read_settings(CONFIG)
  self.assertEqual(c["routingServiceBase"],"https://router.project-osrm.org")
  with self.assertRaises(ValueError):
   m.read_settings(CONFIG.replace("https://photon.komoot.io","http://bad.test"))
  with self.assertRaises(ValueError):
   m.read_settings(CONFIG.replace("https://photon.komoot.io","https://public:secret@bad.test"))
 def test_geojson_road_route_needed(self):
  self.assertFalse(m.validate_routing({"code":"Ok","routes":[]}))
  self.assertFalse(m.validate_routing({"code":"NoRoute","routes":[{"distance":1}]}))
  self.assertTrue(m.validate_routing({"code":"Ok","routes":[{"distance":1000,"duration":100,
   "geometry":{"type":"LineString","coordinates":[[1,2],[3,4]]}}]}))
 def test_geocoding_must_produce_us_result(self):
  self.assertFalse(m.validate_geocode({"features":[]}))
  self.assertFalse(m.validate_geocode({"features":[{"properties":{"countrycode":"GB"},
   "geometry":{"coordinates":[1,2]}}]}))
  self.assertTrue(m.validate_geocode({"features":[{"properties":{"countrycode":"US"},
   "geometry":{"coordinates":[-121,38]}}]}))
 def test_no_user_data_and_failed_provider_is_unknown(self):
  def fetch(url):
   self.assertNotIn("user",url.lower())
   if "/route/" in url:raise TimeoutError("INTERNAL SECRET URL")
   return {"features":[{"properties":{"countrycode":"US"},
                       "geometry":{"coordinates":[-121,38]}}]}
  r=m.check_all(m.read_settings(CONFIG),fetch=fetch)
  self.assertTrue(r["geocoding"]["ok"])
  self.assertFalse(r["routing"]["ok"])
  self.assertEqual(r["routing"]["error_type"],"TimeoutError")
  self.assertNotIn("INTERNAL SECRET",str(r))
if __name__=="__main__":unittest.main()
