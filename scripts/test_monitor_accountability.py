"""Read-only accountability/discovery pipeline monitoring invariants."""
import unittest
from monitor_public_health import assess_public_accountability

def record(kind='government_program',tier='dated_program_disclosure',**updates):
    out={'event_key':'case:1','event_type':kind,'evidence_level':tier,
         'source_url':'https://government.example.gov/file','person_label':None}
    out.update(updates)
    return out

def role():
    return {'role_category':'flock_vendor_leadership',
            'source_type':'official_vendor_announcement',
            'source_url':'https://www.flocksafety.com/blog/example'}

class AccountabilityMonitorTests(unittest.TestCase):
    def test_source_linked_evidence(self):
        self.assertEqual(assess_public_accountability([record()],[role()],1,1),(1,1))
    def test_agenda_cannot_infer_votes(self):
        with self.assertRaisesRegex(ValueError,'individual position'):
            assess_public_accountability([record('agenda_mention',
             'original_government_agenda_mention_only',person_label='Any Council Member')],[role()],1,1)
    def test_contract_form_must_remain_unexecuted(self):
        with self.assertRaisesRegex(ValueError,'signed'):
            assess_public_accountability([record('contract_form_document',
             'editorially_verified_signed_agreement')],[role()],1,1)
    def test_duplicates_and_missing_evidence_fail(self):
        with self.assertRaisesRegex(ValueError,'Duplicated'):
            assess_public_accountability([record(),record()],[role()],1,1)
        with self.assertRaisesRegex(ValueError,'source link'):
            assess_public_accountability([record(source_url='http://bad.example')],[role()],1,1)
    def test_vendor_role_source_is_labelled(self):
        with self.assertRaisesRegex(ValueError,'misattributed'):
            assess_public_accountability([record()],[dict(role(),source_type='press_release')],1,1)
if __name__=='__main__':
    unittest.main()
