"""Offline tests for the live anonymous-access monitor. No live data used."""
import unittest
from unittest.mock import patch
import urllib.error

import monitor_anonymous_access as m

PUBLIC_KEY='sb_publishable_test_public'

class AnonymousBoundaryTests(unittest.TestCase):
 def test_all_sensitive_endpoints_denied(self):
  seen=[]
  def reject(url,key):
   self.assertEqual(key,PUBLIC_KEY)
   self.assertNotIn('password',url)
   self.assertEqual(url.split('?')[0].split('/')[-1] != '',True)
   seen.append(url)
   return 401 if len(seen)%2 else 403
  self.assertEqual(m.check_boundaries(PUBLIC_KEY,reject),
                   len(m.PRIVATE_TABLES)+len(m.PRIVATE_RPC))
  self.assertEqual(len(seen),len(set(seen)))
 def test_empty_success_response_is_not_private(self):
  with self.assertRaisesRegex(ValueError,'accessible'):
   m.check_boundaries(PUBLIC_KEY,lambda url,key:200)
 def test_any_unexpected_response_causes_failure(self):
  for status in (200,206,301,400,404,405,429,500):
   with self.subTest(status=status):
    with self.assertRaises(ValueError):
     m.check_boundaries(PUBLIC_KEY,lambda url,key:status)
 def test_privileged_key_not_allowed(self):
  with self.assertRaisesRegex(ValueError,'Only a public'):
   m.check_boundaries('sb_secret_test_private',lambda url,key:401)
 def test_request_never_reads_200_body(self):
  class MockResponse:
   status=200
   def __enter__(self): return self
   def __exit__(self,*args): return False
   def read(self): raise AssertionError('Private record body must not be read')
  class MockOpener:
   def open(self,*args,**kwargs):return MockResponse()
  with patch.object(m.urllib.request,'build_opener',return_value=MockOpener()):
   self.assertEqual(m.status_only(m.BASE+'/flock_community_submissions',PUBLIC_KEY),200)
 def test_error_status_without_body(self):
  def deny(*args,**kwargs):
   raise urllib.error.HTTPError(m.BASE+'/abc',403,'Forbidden',None,None)
  class MockOpener:
   def open(self,*args,**kwargs):return deny()
  with patch.object(m.urllib.request,'build_opener',return_value=MockOpener()):
   self.assertEqual(m.status_only(m.BASE+'/abc',PUBLIC_KEY),403)
 def test_host_restriction(self):
  with self.assertRaisesRegex(ValueError,'exact production'):
   m.status_only('https://untrusted.example/credentials',PUBLIC_KEY)

if __name__=='__main__':unittest.main()
