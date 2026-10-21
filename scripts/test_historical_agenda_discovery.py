"""Bounded historic Legistar matter discovery and public-record safety tests."""
import urllib.parse
import unittest
from unittest.mock import patch

import discover_government_records as scanner


def matter(mid, title="", name="", notes=""):
    return {
        "MatterId": mid, "MatterTitle": title, "MatterName": name,
        "MatterTypeName": "", "MatterNotes": notes,
    }


class HistoricLegistarTests(unittest.TestCase):
    def test_all_paged_matters_are_checked(self):
        batches = {
            0: [matter(18, "Automatic License Plate Recognition program"),
                matter(17, "Parks budget"),
                matter(16, "Flock Safety camera contract")],
            3: [matter(15, "City hall roof"),
                matter(14, "Public automated license plate readers"),
                matter(13, "Traffic upgrades", notes="ALPR vendor agreement")],
            6: [],
        }
        seen_offsets = []

        def get_page(url):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            offset = int(query["$skip"][0])
            self.assertEqual(int(query["$top"][0]), 3)
            self.assertEqual(query["$orderby"][0], "MatterId desc")
            seen_offsets.append(offset)
            return batches[offset]

        with (patch.object(scanner, "PAGE_SIZE", 3),
              patch.object(scanner, "MAX_PAGES_PER_TENANT", 4),
              patch.object(scanner, "get_json", side_effect=get_page),
              patch.object(scanner, "enrich", return_value="Test-only stub")):
            leads = scanner.scan("madison", "Madison, WI")
        self.assertEqual(seen_offsets, [0, 3, 6])
        self.assertEqual(len(leads), 4)
        self.assertTrue(all(l["status"] == "unreviewed" for l in leads))
        self.assertTrue(all(l["publisher"] == "Madison, WI" for l in leads))
        self.assertEqual(leads[0]["headline"], "Automatic License Plate Recognition program")
        self.assertTrue(all(l["url"].startswith(
            "https://madison.legistar.com/LegislationDetail.aspx?ID=") for l in leads))

    def test_duplicate_api_page_does_not_loop(self):
        duplicate_page = [matter(200, "ALPR"), matter(199, "Other")]
        calls = []

        def get_page(url):
            calls.append(url)
            return duplicate_page

        with (patch.object(scanner, "PAGE_SIZE", 2),
              patch.object(scanner, "MAX_PAGES_PER_TENANT", 8),
              patch.object(scanner, "get_json", side_effect=get_page),
              patch.object(scanner, "enrich", return_value="")):
            leads = scanner.scan("oakland", "Oakland, CA")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(leads), 1)

    def test_historical_scan_has_bounded_requests(self):
        calls = []
        def get_page(url):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            offset = int(query["$skip"][0])
            calls.append(offset)
            return [matter(i, "General council business") for i in
                    range(2000 - offset, 2000 - offset - 3, -1)]

        with (patch.object(scanner, "PAGE_SIZE", 3),
              patch.object(scanner, "MAX_PAGES_PER_TENANT", 4),
              patch.object(scanner, "get_json", side_effect=get_page),
              patch.object(scanner, "enrich", return_value="")):
            leads = scanner.scan("seattle", "Seattle, WA")
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls, [0, 3, 6, 9])
        self.assertEqual(leads, [])

    def test_invalid_api_response_fails_closed(self):
        with patch.object(scanner, "get_json", return_value={"error": "temporary"}):
            with self.assertRaises(ValueError):
                scanner.scan("cabq", "Albuquerque, NM")

    def test_only_specific_keywords_match(self):
        self.assertTrue(scanner.TERMS.search("License Plate Readers"))
        self.assertTrue(scanner.TERMS.search("Automatic License Plate Recognition"))
        self.assertTrue(scanner.TERMS.search("Automated License Plate Reader"))
        self.assertTrue(scanner.TERMS.search("Flock Safety"))
        self.assertTrue(scanner.TERMS.search("ALPR"))
        self.assertFalse(scanner.TERMS.search("Regular water budget"))


if __name__ == "__main__":
    unittest.main()
