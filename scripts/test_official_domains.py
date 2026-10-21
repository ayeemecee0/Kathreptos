"""Safety tests for evidence-reviewed custom government domains.

Run: python -m unittest discover -s scripts -p 'test_*.py' -v
"""
import unittest
from unittest.mock import patch

import government_domain_registry as domains
import discover_source_registry as discovery
import verify_government_sources as verifier


def approved_rows():
    return [{
        "domain": "cityofmadison.com",
        "jurisdiction_label": "Madison, WI",
        "legistar_tenant": "madison",
        "legistar_evidence_url":
            "https://www.cityofmadison.com/council/district10/blog/2021-11-22/city-of-madison-website-navigation-tips-legistar",
        "allow_www": True,
        "verification_status": "verified",
        "evidence_url": "https://lobbying.wi.gov/example",
        "reviewed_by": "operator",
        "reviewed_at": "2026-10-20T20:00:00Z",
    }]


class GovernmentDomainTests(unittest.TestCase):
    def setUp(self):
        self.approved = domains.parse_verified_rows(approved_rows())

    def test_approved_exact_and_www(self):
        self.assertIsNotNone(domains.official_url("https://cityofmadison.com/", self.approved))
        self.assertIsNotNone(domains.official_url("https://www.cityofmadison.com/council", self.approved))

    def test_no_wildcard_or_lookalike(self):
        for url in (
            "https://cityofmadison.com.evil.com/",
            "https://fake.cityofmadison.com/",
            "https://evilcityofmadison.com/",
            "https://www.cityofmadison.com.evil.org/",
            "https://cityofmadison.org/",
            "http://www.cityofmadison.com/",
            "https://user:secret@www.cityofmadison.com/",
            "https://www.cityofmadison.com:8080/",
            "https://www.cityofmadison.com\\@evil.com/",
        ):
            with self.subTest(url=url):
                self.assertIsNone(domains.official_url(url, self.approved))

    def test_dot_gov_is_not_any_gov_string(self):
        self.assertIsNotNone(domains.official_url("https://www.mountainview.gov/", self.approved))
        for url in ("https://town.gov.evil.com/", "https://evilgov.com/",
                    "https://town.gov.org/"):
            self.assertIsNone(domains.official_url(url, self.approved))

    def test_candidate_domains_never_authorized(self):
        rows = approved_rows()
        rows[0]["verification_status"] = "candidate"
        self.assertEqual(domains.parse_verified_rows(rows), {})

    def test_missing_review_or_bad_authority_is_rejected(self):
        for field, value in (("reviewed_by", ""), ("reviewed_at", None),
                             ("evidence_url", "https://fake.gov.evil.com/")):
            with self.subTest(field=field):
                rows = approved_rows()
                rows[0][field] = value
                with self.assertRaises(ValueError):
                    domains.parse_verified_rows(rows)

    def test_unreviewed_hostname_substitution_is_rejected(self):
        rows = approved_rows()
        rows[0]["legistar_evidence_url"] = "https://madison.legistar.com/"
        with self.assertRaises(ValueError):
            domains.parse_verified_rows(rows)

    def test_tenant_binding_is_exact(self):
        page = "https://www.cityofmadison.com/council"
        self.assertEqual(
            domains.approved_tenant_for_page(page, "madison", self.approved), "Madison, WI")
        self.assertIsNone(domains.approved_tenant_for_page(page, "commerce", self.approved))
        self.assertIsNone(domains.approved_tenant_for_page(
            "https://www.cityofmadison.com.evil.com/", "madison", self.approved))

    def test_curated_evidence_url_is_accepted(self):
        pages = domains.approved_evidence_pages(self.approved)
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0].startswith("https://www.cityofmadison.com/"))

    def test_discovery_rejects_unreviewed_custom_sources(self):
        self.assertIsNone(discovery.candidate(
            "https://www.unapproved-government.com/", "government_portal",
            approved=self.approved))
        self.assertIsNotNone(discovery.candidate(
            "https://www.cityofmadison.com/council", "government_portal",
            approved=self.approved))

    def test_custom_approved_identity_not_search_snippet(self):
        page = discovery.GovernmentPage()
        page.feed("<html><title>Common Council | City of Madison</title>"
                  "<a href='https://madison.legistar.com/Calendar.aspx'>Meeting schedule</a></html>")
        page.close()
        label = discovery.identity_for_tenant(
            page, "https://madison.legistar.com/",
            "https://www.cityofmadison.com/council", self.approved)
        self.assertEqual(label, "Madison, WI")
        self.assertIsNone(discovery.identity_for_tenant(
            page, "https://commerce.legistar.com/",
            "https://www.cityofmadison.com/council", self.approved))

    def test_verifier_approves_only_matching_live_government_page(self):
        page_html = ("<html><title>City of Madison</title><body>Madison, WI"
                     "<a href='https://madison.legistar.com/Calendar.aspx'>Agenda</a>"
                     "</body></html>")
        row = {
            "source_url": "https://madison.legistar.com/",
            "evidence_url": "https://www.cityofmadison.com/council",
            "jurisdiction_label": "Madison, WI",
        }
        with (patch.object(verifier, "safe_official_url", return_value=True),
              patch.object(verifier, "fetch_official_html",
                           return_value=(page_html, row["evidence_url"])),
              patch.object(verifier, "legistar_api_valid", return_value=True)):
            ok, reason = verifier.verify(row, self.approved)
            self.assertTrue(ok, reason)

    def test_verifier_denies_cross_jurisdiction_link(self):
        row = {
            "source_url": "https://commerce.legistar.com/",
            "evidence_url": "https://www.cityofmadison.com/council",
            "jurisdiction_label": "Commerce City, CO",
        }
        with patch.object(verifier, "safe_official_url", return_value=True):
            ok, _ = verifier.verify(row, self.approved)
        self.assertFalse(ok)

    def test_verifier_denies_wrong_label_for_right_tenant(self):
        row = {
            "source_url": "https://madison.legistar.com/",
            "evidence_url": "https://www.cityofmadison.com/council",
            "jurisdiction_label": "Madison, AL",
        }
        with patch.object(verifier, "safe_official_url", return_value=True):
            ok, _ = verifier.verify(row, self.approved)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
