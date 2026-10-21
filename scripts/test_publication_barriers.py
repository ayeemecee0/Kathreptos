"""Publication barriers: public discovery must not bypass editorial review."""
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

import discover_official


class ReviewOnlyDiscoveryTests(unittest.TestCase):
    def test_verified_looking_municipal_page_is_queued_not_published(self):
        sample = {
            "state": "CA", "city": "Demo City",
            "agency": "City of Demo City", "publisher": "City of Demo City",
        }
        page = "https://demo-city.gov/flock-public-policy"
        with (patch.object(discover_official, "collect", return_value=[page]),
              patch.object(discover_official, "fetch_text", return_value="Flock Safety ALPR"),
              patch.object(discover_official, "identify", return_value=sample),
              patch.object(discover_official, "queue_for_review", return_value=201) as queue,
              patch.dict("os.environ", {
                  "SUPABASE_URL": "https://example.supabase.co",
                  "SUPABASE_SERVICE_ROLE_KEY": "test-key",
              })):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                discover_official.main()
        self.assertEqual(queue.call_count, 1)
        self.assertEqual(queue.call_args.args[0], page)
        self.assertIn("auto-published: 0", out.getvalue())

    def test_scheduled_discovery_has_no_publication_script(self):
        text = Path(".github/workflows/discover.yml").read_text(encoding="utf-8")
        self.assertNotIn("run: python scripts/auto_publish_official.py", text)
        self.assertNotIn("run: python scripts/publish", text)


if __name__ == "__main__":
    unittest.main()
