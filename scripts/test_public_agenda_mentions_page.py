"""Public site must distinguish verified agenda mentions from government actions."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = False
        self.js = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = not any(k == "src" for k, v in attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = False

    def handle_data(self, value):
        if self.current and value.strip():
            self.js.append(value)


class PublicAgendaPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "records.html").read_text(encoding="utf-8")
        parser = InlineScripts()
        parser.feed(cls.html)
        cls.js = "\n".join(parser.js)

    def test_js_syntax(self):
        if not shutil.which("node"):
            self.skipTest("Node unavailable")
        proc = subprocess.run(
            ["node", "--check"], input=self.js, capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_public_agenda_mentions_are_not_labeled_as_contract_approvals(self):
        self.assertIn('verified_flock_agenda_mentions', self.js)
        self.assertIn('No approval inferred', self.js)
        self.assertIn('agenda listing only', self.js)
        self.assertIn('not contract approvals', self.js)
        self.assertIn('Official agenda mentions', self.html)

    def test_public_content_is_rendered_as_text(self):
        self.assertIn("textContent", self.js)
        self.assertNotIn(".innerHTML", self.js)
        self.assertIn("noopener noreferrer", self.js)


if __name__ == "__main__":
    unittest.main()
