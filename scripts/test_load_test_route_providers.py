import unittest
from unittest.mock import patch
import load_test_route_providers as s

class ProviderLoadAcceptance(unittest.TestCase):
 def test_refuses_shared_demos_and_untrusted_urls(self):
  for url in ("https://photon.komoot.io","https://router.project-osrm.org",
       "http://example.com","https://u:p@example.com","https://127.0.0.1",
       "https://router.example.com/?api_key=token"):
   with self.assertRaises(ValueError):s.validate_base(url)
 def test_bounded_fixed_us_routes_and_geocoding(self):
  seen=[]
  def fixture(url):
   seen.append(url)
   if "/route/" in url:
    return {"code":"Ok","routes":[{"distance":1000,
             "geometry":{"type":"LineString","coordinates":[[-121,38],[-120,38]]}}]}
   return {"features":[{"geometry":{"coordinates":[-121,38]},
                         "properties":{"countrycode":"US"}}]}
  result=s.run_test("https://routing.example.com","https://geocode.example.com",
       rounds=2,workers=4,fetch=fixture)
  self.assertEqual(result["routing"]["passed"],16)
  self.assertEqual(result["geocoding"]["passed"],16)
  self.assertEqual(result["routing"]["failed"],0)
  self.assertEqual(len(seen),32)
  self.assertTrue(all("Sacramento" not in url or "q=" in url for url in seen))
 def test_malformed_schema_fails_no_absence_claim(self):
  x=s.run_test("https://routing.example.com","https://geo.example.com",1,1,
      fetch=lambda url: {"routes":[]})
  self.assertEqual(x["routing"]["failed"],8)
  self.assertEqual(x["geocoding"]["failed"],8)
 def test_bounding_controls(self):
  for k in (0,5):
   with self.assertRaises(ValueError):
    s.run_test("https://routing.example.com","https://geo.example.com",rounds=k)
   with self.assertRaises(ValueError):
    s.run_test("https://routing.example.com","https://geo.example.com",workers=k)

if __name__=="__main__":unittest.main()
