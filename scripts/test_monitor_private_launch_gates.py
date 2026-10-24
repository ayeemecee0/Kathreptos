"""Offline tests: private bucket must fail closed and public-facing CI prints counts only."""
import unittest
from unittest.mock import patch
import monitor_private_launch_gates as m

KEY='sb_secret_TEST_SERVER_SIDE_ONLY'
BUCKET={'id':m.BUCKET,'public':False,'file_size_limit':3145728,
        'allowed_mime_types':['image/jpeg','image/png','image/webp']}

def safe_fetch(method,url,key):
    assert key==KEY and url.startswith(m.PROJECT+'/')
    if method=='GET':
        return dict(BUCKET)
    assert method=='HEAD'
    assert 'limit=1' in url
    assert 'select=' in url
    # Exact count is a header, not a download of any candidate row.
    return ('0-0/293' if '/flock_camera_locations?' in url else
            '0-0/1' if '/first_party_agency_gis_receipts?' in url else '*/0')

class LaunchGates(unittest.TestCase):
 def test_private_bucket_and_aggregate_counts_pass(self):
    totals=m.tally(KEY,safe_fetch)
    self.assertEqual(totals['verified_exact_camera_points'],293)
    self.assertEqual(totals['first_party_agency_source_receipts'],1)
    self.assertEqual(totals['direct_government_gis_receipts'],0)
    self.assertEqual(set(totals),{x[0] for x in m.STAGES})
 def test_bucket_must_remain_private(self):
    for bad in ({**BUCKET,'public':True},{**BUCKET,'public':None},
                {**BUCKET,'id':'other'}, {}, None):
        with self.subTest(bad=bad):
            with self.assertRaises(ValueError):
                m.verify_bucket(bad)
 def test_file_restrictions_are_mandatory(self):
    for bad in ({**BUCKET,'file_size_limit':None},
                {**BUCKET,'file_size_limit':3145729},
                {**BUCKET,'allowed_mime_types':None},
                {**BUCKET,'allowed_mime_types':['image/png','application/pdf']},
                {**BUCKET,'allowed_mime_types':[]}):
        with self.subTest(bad=bad):
            with self.assertRaises(ValueError):
                m.verify_bucket(bad)
 def test_exact_counts_fail_closed(self):
    for bad in (None,'','0-0/*','200','*/NaN','0-9/1000012'):
        with self.subTest(header=bad):
            with self.assertRaises(ValueError):
                m.extract_count(bad)
    self.assertEqual(m.extract_count('*/0'),0)
    self.assertEqual(m.extract_count('0-0/10399'),10399)
 def test_untrusted_service_key_is_refused(self):
    for key in ('','sb_publishable_NOT_SERVER_KEY','abc'):
        with self.assertRaises(ValueError):
            m.tally(key,safe_fetch)
 def test_live_drop_must_stop_release(self):
    def dropped(method,url,key):
        if method=='HEAD' and '/flock_camera_locations?' in url:
            return '*/0'
        return safe_fetch(method,url,key)
    with self.assertRaisesRegex(ValueError,'below reviewed baseline'):
        m.tally(KEY,dropped)
 def test_missing_header_or_bucket_data_does_not_pass(self):
    def no_count(method,url,key):
        if method=='HEAD':return None
        return safe_fetch(method,url,key)
    with self.assertRaisesRegex(ValueError,'header missing'):
        m.tally(KEY,no_count)
    def public_bucket(method,url,key):
        if method=='GET':return {**BUCKET,'public':True}
        return safe_fetch(method,url,key)
    with self.assertRaisesRegex(ValueError,'publicly exposed'):
        m.tally(KEY,public_bucket)
 def test_transport_refuses_private_data_get(self):
    with self.assertRaisesRegex(ValueError,'Only the fixed private bucket'):
        m.transport('GET',m.PROJECT+'/rest/v1/flock_community_submissions',KEY)
    with self.assertRaisesRegex(ValueError,'arbitrary'):
        m.transport('HEAD','https://untrusted.example/secrets',KEY)
    with self.assertRaisesRegex(ValueError,'Read-only'):
        m.transport('DELETE',m.PROJECT+'/storage/v1/bucket/'+m.BUCKET,KEY)

if __name__=='__main__':unittest.main()
