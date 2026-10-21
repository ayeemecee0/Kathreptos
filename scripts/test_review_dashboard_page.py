"""Static safeguards and syntax validation for the reviewer-only browser app."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "review.html"
EDGE = ROOT / "supabase/functions/review-evidence/index.ts"


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inline = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = not any(k == "src" for k, _ in attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script and data.strip():
            self.inline.append(data)


class ReviewerPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        parser = Scripts()
        parser.feed(cls.html)
        cls.js = "\n".join(parser.inline)
        cls.edge = EDGE.read_text(encoding="utf-8")

    def test_inline_script_is_valid_js(self):
        if not shutil.which("node"):
            self.skipTest("Node.js is not installed")
        checked = subprocess.run(
            ["node", "--check"], input=self.js, text=True,
            capture_output=True, timeout=10)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_private_data_uses_authenticated_apis_not_service_key(self):
        self.assertIn("client.rpc('editorial_session')", self.js)
        self.assertIn("client.rpc('editorial_decide'", self.js)
        self.assertIn("client.rpc('editorial_general_decide'", self.js)
        self.assertIn("client.rpc('editorial_history'", self.js)
        self.assertNotIn("service_role", self.html.lower())
        self.assertNotIn("SB_SECRET_KEY", self.html)
        self.assertNotIn("supabase_service_role", self.edge.lower())

    def test_approval_and_publication_are_separate(self):
        self.assertIn("Approve evidence (private)", self.html)
        self.assertIn("Publish reviewed decision", self.html)
        self.assertIn("Accept lead (private)", self.html)
        self.assertIn("status='published'", (ROOT / "supabase/migrations/010_editorial_dashboard_auth_and_rpc.sql").read_text())
        self.assertIn("v_role <> 'publisher'", (ROOT / "supabase/migrations/010_editorial_dashboard_auth_and_rpc.sql").read_text())

    def test_all_untrusted_content_rendered_as_text(self):
        self.assertIn("textContent", self.js)
        self.assertNotIn(".innerHTML", self.js)
        self.assertIn("noopener noreferrer", self.js)
        self.assertIn('u.protocol!==\'https:\'', self.js)

    def test_evidence_reader_cannot_proxy_arbitrary_urls(self):
        self.assertIn('review_id: id', self.js)
        self.assertIn("editorial_evidence_ref", self.edge)
        self.assertIn('"https://webapi.legistar.com/v1/"', self.edge)
        self.assertNotIn("fetch(input.url", self.edge)


if __name__ == "__main__":
    unittest.main()
