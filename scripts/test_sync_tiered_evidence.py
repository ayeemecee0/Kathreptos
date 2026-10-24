import unittest
from unittest.mock import patch
import sync_tiered_evidence as s

class TrustedEvidenceBridgeTests(unittest.TestCase):
    def test_stage_then_reconcile_without_approval_argument(self):
        staged=[{"staged_cases":3,"staged_osm_attestations":3,
                 "reverified_government_attestations":1},
                {"staged_cases":0,"staged_osm_attestations":0,
                 "reverified_government_attestations":1},
                {"government_qualified":0,"corroborated_qualified":0}]
        with patch.object(s,"api_request",side_effect=staged) as request:
            totals=s.run(rounds=4,limit=30)
        self.assertEqual(request.call_count,3)
        self.assertEqual(request.call_args_list[0].args[0],
                        "rpc/stage_tiered_evidence_from_verified_matches")
        self.assertEqual(request.call_args_list[-1].args[0],
                        "rpc/reconcile_tiered_evidence_cases")
        for call in request.call_args_list:
            self.assertEqual(call.kwargs["payload"],{"p_limit":30})
            self.assertEqual(call.kwargs["method"],"POST")
        self.assertEqual(totals["staged_cases"],3)
    def test_reject_unbounded_or_invalid_inputs(self):
        with patch.object(s,"api_request") as request:
            for limit in (0,601,-1):
                with self.assertRaises(ValueError):s.invoke("stage_tiered_evidence_from_verified_matches",limit)
            with self.assertRaises(ValueError):s.run(rounds=19)
            request.assert_not_called()
    def test_reject_malformed_database_result(self):
        with patch.object(s,"api_request",return_value={"staged_cases":"20"}):
            with self.assertRaises(ValueError):s.invoke("stage_tiered_evidence_from_verified_matches",100)
        with patch.object(s,"api_request",return_value=[{"staged_cases":1}]):
            with self.assertRaises(ValueError):s.invoke("stage_tiered_evidence_from_verified_matches",100)

if __name__=="__main__":unittest.main()
