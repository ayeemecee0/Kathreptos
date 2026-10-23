import unittest
from unittest.mock import Mock
from paged_supabase import fetch_all
class PaginatedSourceRegistry(unittest.TestCase):
 def test_fetches_multiple_deterministic_pages(self):
  provider=Mock(side_effect=[[{"source_key":str(i)} for i in range(25)],
                             [{"source_key":"26"}]])
  rows=fetch_all(provider,"gis_sources?select=source_key&source_status=eq.verified&limit=100",
                 "source_key")
  self.assertEqual(len(rows),26)
  self.assertEqual(provider.call_count,2)
  self.assertIn("order=source_key.asc",provider.call_args_list[0].args[0])
  self.assertIn("offset=25",provider.call_args_list[1].args[0])
 def test_exact_full_capacity_is_unknown_not_complete(self):
  provider=Mock(return_value=[{"source_key":str(i)} for i in range(25)])
  with self.assertRaisesRegex(ValueError,"exceeds"):
   fetch_all(provider,"x?select=source_key","source_key",25,50)
 def test_malformed_page_never_returns_partial_success(self):
  provider=Mock(side_effect=[[{}]*25,{"error":"timeout"}])
  with self.assertRaisesRegex(ValueError,"invalid"):
   fetch_all(provider,"x?select=source_key","source_key")
 def test_unsafe_parameters_rejected(self):
  with self.assertRaises(ValueError):
   fetch_all(Mock(),"x?select=id","id;drop")
  with self.assertRaises(ValueError):
   fetch_all(Mock(),"x?offset=100","id")
if __name__=="__main__":unittest.main()
