"""Never conflate official Flock agenda mentions with government approvals.

These tests intentionally mock official API replies. The production verifier
performs a new HTTPS GET of the exact official matter before any public insert.
"""
import unittest
from unittest.mock import patch

import auto_verify_flock_agenda as verifier


def staged(tenant="commerce", mid=12379, state="needs_primary_review"):
    return {
        "tenant": tenant, "matter_id": mid, "review_state": state,
        "official_api_url": f"https://webapi.legistar.com/v1/{tenant}/matters/{mid}",
    }


def api_matter(mid=12379, title="Flock Safety - Safe Cities Program",
               restrict=False, **kwargs):
    return {
        "MatterId": mid,
        "MatterTitle": title,
        "MatterName": "",
        "MatterIntroDate": "2026-04-06T00:00:00",
        "MatterFile": "PRES 2026-10",
        "MatterRestrictViewViaWeb": restrict,
        **kwargs,
    }


VERIFIED = {
    "commerce": {
        "jurisdiction_label": "Commerce City, CO",
        "government_evidence_url": "https://www.c3gov.com/Government/City-Council",
    },
}


class AutomaticAgendaMentionTests(unittest.TestCase):
    def test_direct_official_flock_safety_title_is_only_narrow_claim(self):
        with patch.object(verifier, "get_json", return_value=api_matter()) as get:
            result, reason = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(reason)
        self.assertEqual(result["tenant"], "commerce")
        self.assertEqual(result["matter_id"], 12379)
        self.assertEqual(result["matter_title"], "Flock Safety - Safe Cities Program")
        self.assertEqual(result["intro_date"], "2026-04-06")
        self.assertEqual(result["jurisdiction_label"], "Commerce City, CO")
        self.assertNotIn("approved", result)
        self.assertNotIn("signed", result)
        self.assertNotIn("camera_count", result)
        get.assert_called_once_with(
            "https://webapi.legistar.com/v1/commerce/matters/12379")

    def test_alpr_title_without_named_vendor_never_qualifies(self):
        with patch.object(verifier, "get_json",
                          return_value=api_matter(title="Automated License Plate Readers Policy")):
            result, reason = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(result)
        self.assertIn("does not explicitly name", reason)

    def test_flok_brand_from_untrusted_search_snippet_never_qualifies(self):
        row = staged()
        row["headline"] = "Flock Safety council meeting"
        with patch.object(verifier, "get_json",
                          return_value=api_matter(title="Public Safety Camera Discussion")):
            result, _ = verifier.official_mention(row, VERIFIED)
        self.assertIsNone(result)

    def test_wrong_official_api_matter_id_rejected(self):
        with patch.object(verifier, "get_json",
                          return_value=api_matter(mid=999999)):
            result, reason = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(result)
        self.assertIn("MatterId mismatch", reason)

    def test_staged_wrong_source_url_rejected_before_network(self):
        row = staged()
        row["official_api_url"] = "https://webapi.legistar.com/v1/commerce/matters/9999"
        with patch.object(verifier, "get_json") as get:
            result, reason = verifier.official_mention(row, VERIFIED)
        self.assertIsNone(result)
        self.assertIn("identity mismatch", reason)
        get.assert_not_called()

    def test_unverified_tenant_never_contacted(self):
        with patch.object(verifier, "get_json") as get:
            result, reason = verifier.official_mention(staged("badtenant"), VERIFIED)
        self.assertIsNone(result)
        get.assert_not_called()

    def test_restricted_official_matter_is_held(self):
        with patch.object(verifier, "get_json",
                          return_value=api_matter(restrict=True)):
            result, reason = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(result)
        self.assertIn("not publicly viewable", reason)

    def test_deleted_official_matter_is_held(self):
        with patch.object(verifier, "get_json",
                          return_value=api_matter(MatterDeleted=True)):
            result, reason = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(result)
        self.assertIn("not publicly viewable", reason)

    def test_rejected_or_existing_published_decision_never_republished(self):
        with patch.object(verifier, "get_json") as get:
            for state in ("rejected", "published"):
                result, reason = verifier.official_mention(staged(state=state), VERIFIED)
                self.assertIsNone(result)
        get.assert_not_called()

    def test_empty_or_mismatched_response_is_held(self):
        with patch.object(verifier, "get_json", return_value=[]):
            result, _ = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(result)

    def test_date_is_evidence_intro_not_vote(self):
        with patch.object(verifier, "get_json",
                          return_value=api_matter(MatterIntroDate="not-a-date")):
            result, reason = verifier.official_mention(staged(), VERIFIED)
        self.assertIsNone(reason)
        self.assertIsNone(result["intro_date"])

    def test_user_supplied_claim_fields_are_not_transferred(self):
        row = staged()
        row["action_date"] = "2026-10-20"
        row["decision_outcome"] = "approved"
        row["signed_on"] = "2026-10-20"
        with patch.object(verifier, "get_json", return_value=api_matter()):
            claim, reason = verifier.official_mention(row, VERIFIED)
        self.assertIsNone(reason)
        for key in ("action_date", "decision_outcome", "signed_on"):
            self.assertNotIn(key, claim)

    def test_duplicate_published_mention_is_reported_not_overwritten(self):
        with (patch.object(verifier, "api_request", return_value=[]) as request):
            self.assertFalse(verifier.submit_verified_mention({
                "tenant": "commerce", "matter_id": 12379,
                "jurisdiction_label": "Commerce City, CO",
                "matter_title": "Flock Safety - Safe Cities Program",
                "government_evidence_url": "https://www.c3gov.com/",
            }))
        self.assertIn("resolution=ignore-duplicates",
                      request.call_args.kwargs["prefer"])

    def test_no_public_actions_contracts_or_deployments_touched(self):
        source = verifier.__doc__
        self.assertIn("NOT proof", source)
        with (patch.object(verifier, "registry_clients", return_value={
                "commerce": "Commerce City, CO"}),
              patch.object(verifier, "verified_registry_rows",
                           return_value=VERIFIED),
              patch.object(verifier, "staged_candidates",
                           return_value=[staged()]),
              patch.object(verifier, "get_json", return_value=api_matter()),
              patch.object(verifier, "submit_verified_mention", return_value=True)
              as submit):
            verifier.main()
            submit.assert_called_once()
        self.assertIn("government_evidence_url", submit.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
