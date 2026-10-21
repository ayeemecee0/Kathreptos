"""Fail-closed regression tests for automatic government legislative decisions."""
import datetime as dt
import unittest
from unittest.mock import patch

import auto_verify_legislative_decisions as decisions


PARENT = {
    "tenant": "oakland", "matter_id": 36760,
    "jurisdiction_label": "Oakland, CA",
    "matter_title": "OPD Community Safety Cameras And Flock Safety Contract",
    "file_number": "26-0189", "status": "verified",
}
STAGED = {
    "tenant": "oakland", "matter_id": 36760,
    "review_state": "source_verified",
    "official_api_url": "https://webapi.legistar.com/v1/oakland/matters/36760",
}
REGISTRY = {
    "oakland": {
        "jurisdiction_label": "Oakland, CA",
        "government_evidence_url": "https://oakland.legistar.com/",
    },
}


def record(action="Failed", flag="Failed", body="City Council",
           date="2025-11-18T00:00:00", hid=35):
    return {
        "MatterHistoryId": hid,
        "MatterHistoryActionName": action,
        "MatterHistoryPassedFlagName": flag,
        "MatterHistoryActionBodyName": body,
        "MatterHistoryActionDate": date,
    }


class StructuredDecisionTests(unittest.TestCase):
    def check(self, event, **kwargs):
        payload, reason = decisions.exact_action_event(
            event, PARENT, today=dt.date(2026, 10, 20))
        for key, expected in kwargs.items():
            self.assertEqual(payload[key], expected, reason)
        return payload, reason

    def test_exact_failed_council_action(self):
        payload, _ = self.check(record(), decision_outcome="failed",
                                action_date="2025-11-18", history_id=35)
        self.assertEqual(payload["action_body"], "City Council")
        self.assertEqual(payload["matter_id"], 36760)
        self.assertNotIn("contract", payload)
        self.assertNotIn("votes", payload)
        self.assertNotIn("final_disposition", payload)

    def test_adopted_as_amended_passed(self):
        self.check(record(action="Adopted as Amended", flag="Pass",
                          body="City Council"),
                   decision_outcome="adopted_as_amended")

    def test_approved_recorded_by_board_of_supervisors(self):
        self.check(record(action="Approved", flag="Passed",
                          body="Board of Supervisors"),
                   decision_outcome="approved")

    def test_no_mislabeled_pass_fail(self):
        for action, flag in (("Adopted", "Failed"), ("Failed", "Passed"),
                             ("Approved", "Yes"), ("Rejected", None),
                             ("Adopted", ""), ("Failed", "Pass")):
            with self.subTest(action=action, flag=flag):
                p, reason = decisions.exact_action_event(
                    record(action=action, flag=flag), PARENT)
                self.assertIsNone(p)
                self.assertIn("pass/fail", reason)

    def test_committee_cannot_be_published_as_council(self):
        for body in ("Public Safety Committee", "City Council Finance Committee",
                     "Finance and Management Committee", "City Manager",
                     "Committee of the Whole", "Planning Commission"):
            with self.subTest(body=body):
                p, reason = decisions.exact_action_event(
                    record(body=body), PARENT)
                self.assertIsNone(p)
                self.assertIn("governing body", reason)

    def test_proposal_and_reading_are_not_votes(self):
        for action in ("Recommended for Adoption", "Passed on First Reading",
                       "Introduced", "Referred", "Received", "Discussed",
                       "Filed", "Adopted on First Reading", "Recommended as Amended"):
            with self.subTest(action=action):
                p, reason = decisions.exact_action_event(
                    record(action=action, flag="Passed"), PARENT)
                self.assertIsNone(p)
                self.assertIn("not an unequivocal", reason)

    def test_id_and_date_validation(self):
        for event in (
            record(hid=0), record(hid="35"), record(hid=True),
            record(date="2029-01-01"), record(date="bad date"),
            record(date="1989-12-31"), record(date=None),
        ):
            p, _ = decisions.exact_action_event(
                event, PARENT, today=dt.date(2026,10,20))
            self.assertIsNone(p)

    def test_status_not_inferred_from_history_item(self):
        event=record(action="Adopted",flag="Passed")
        event["MatterHistoryActionText"]="Signed contract and paid $5 million"
        p,reason=decisions.exact_action_event(event,PARENT)
        self.assertIsNone(reason)
        self.assertNotIn("action_text",p)
        self.assertNotIn("signed_contract",p)
        self.assertEqual(p["decision_outcome"],"adopted")

    def test_parent_title_rechecked_against_official_api(self):
        with (patch.object(decisions, "official_mention",
                           return_value=({**PARENT,"matter_title":
                               "Different Flock Safety Contract"},None)) as verify,
              patch.object(decisions, "get_json") as get):
            events,reason=decisions.get_history_events(STAGED,REGISTRY,PARENT)
        self.assertEqual(events,[])
        self.assertIn("title or file changed",reason)
        verify.assert_called_once()
        get.assert_not_called()

    def test_no_official_government_authority(self):
        with patch.object(decisions,"official_mention") as verify:
            events,reason=decisions.get_history_events(STAGED,{},PARENT)
            self.assertEqual(events,[])
            verify.assert_not_called()

    def test_rejected_or_published_not_reopened_by_automation(self):
        for state in ("rejected","published"):
            with patch.object(decisions,"official_mention") as verify:
                events,_=decisions.get_history_events(
                    {**STAGED,"review_state":state},REGISTRY,PARENT)
                self.assertEqual(events,[])
                verify.assert_not_called()

    def test_conflicting_duplicate_history_id_is_not_published(self):
        histories=[record(hid=20,action="Adopted",flag="Passed"),
                   record(hid=20,action="Failed",flag="Failed"),
                   record(hid=21,action="Failed",flag="Failed")]
        with (patch.object(decisions,"official_mention",
                           return_value=(PARENT,None)),
              patch.object(decisions,"get_json",return_value=histories)):
            rows,reason=decisions.get_history_events(STAGED,REGISTRY,PARENT)
        self.assertEqual([r["history_id"] for r in rows],[21])
        self.assertIn("conflicting",reason)

    def test_malformed_and_oversize_histories_fail_closed(self):
        for value in ({"message":"not array"},[{}]*201):
            with (patch.object(decisions,"official_mention",
                               return_value=(PARENT,None)),
                  patch.object(decisions,"get_json",return_value=value)):
                rows,_=decisions.get_history_events(STAGED,REGISTRY,PARENT)
                self.assertEqual(rows,[])

    def test_idempotent_insert_without_override(self):
        with patch.object(decisions,"api_request",return_value=[]) as api:
            self.assertFalse(decisions.insert_verified_decision(
                {"tenant":"oakland","matter_id":36760,"history_id":35}))
        self.assertIn("resolution=ignore-duplicates",api.call_args.kwargs["prefer"])
        self.assertIn("tenant,matter_id,history_id",api.call_args.args[0])

    def test_dry_run_cannot_publish(self):
        with (patch.object(decisions,"registry_clients",return_value={"oakland":"Oakland, CA"}),
              patch.object(decisions,"verified_registry_rows",return_value=REGISTRY),
              patch.object(decisions,"fetch_public_mentions",
                           return_value={("oakland",36760):PARENT}),
              patch.object(decisions,"staged_candidates",return_value=[STAGED]),
              patch.object(decisions,"get_history_events",
                           return_value=([{
                               **PARENT,"history_id":35,
                               "decision_outcome":"failed",
                               "action_name":"Failed","action_body":"City Council",
                               "passed_flag_name":"Failed","action_date":"2025-11-18"}],None)),
              patch.object(decisions,"insert_verified_decision") as insert):
            result=decisions.run(dry_run=True)
        self.assertEqual(result["eligible"],1)
        self.assertEqual(result["published"],0)
        insert.assert_not_called()

    def test_actual_run_submits_only_explicit_events(self):
        payload,_=decisions.exact_action_event(record(),PARENT)
        with (patch.object(decisions,"registry_clients",return_value={"oakland":"Oakland, CA"}),
              patch.object(decisions,"verified_registry_rows",return_value=REGISTRY),
              patch.object(decisions,"fetch_public_mentions",
                           return_value={("oakland",36760):PARENT}),
              patch.object(decisions,"staged_candidates",return_value=[STAGED]),
              patch.object(decisions,"get_history_events",
                           return_value=([payload],None)),
              patch.object(decisions,"insert_verified_decision",return_value=True) as insert):
            result=decisions.run()
        self.assertEqual(result["published"],1)
        insert.assert_called_once_with(payload)


if __name__=="__main__":
    unittest.main()
