"""Offline regression tests for the PUBLIC-ONLY snapshot allowlist."""
import unittest
from snapshot_public_evidence import verify_allowlist,validate_payload,create_snapshot

def example():
 return {
   'overview':[{'exact_government_points':1,'accountability_records':1,
                'states_with_any_documented_evidence':1,
                'documented_individual_positions':0}],
   'states':[{'state_code':'CA'}],
   'monthly_evidence':[],
   'government_accountability':[{'event_key':'document:1','source_url':'https://city.example.gov/agenda'}],
   'individual_official_positions':[],
   'verified_camera_points':[{'record_key':'original-gis:1'}],
 }

class PublicSnapshotTests(unittest.TestCase):
 def test_allowlist(self):
    verify_allowlist()
 def test_consistent_published_counts(self):
    self.assertTrue(validate_payload(example()))
    snapshot=create_snapshot(example())
    self.assertEqual(len(snapshot['sha256_of_data']),64)
    self.assertEqual(snapshot['scope'],'ANONYMOUS_PUBLIC_EVIDENCE_ONLY')
 def test_fail_on_mismatched_totals(self):
    data=example();data['overview'][0]['accountability_records']=2
    with self.assertRaisesRegex(ValueError,'reconciliation'):
        validate_payload(data)
 def test_fail_on_unsourced_claims(self):
    data=example();data['government_accountability'][0]['source_url']='http://invalid.example'
    with self.assertRaisesRegex(ValueError,'HTTPS source'):
        validate_payload(data)
 def test_duplicate_claim(self):
    data=example()
    data['government_accountability'].append(dict(data['government_accountability'][0]))
    data['overview'][0]['accountability_records']=2
    with self.assertRaisesRegex(ValueError,'Duplicate'):
        validate_payload(data)

if __name__=='__main__':unittest.main()
