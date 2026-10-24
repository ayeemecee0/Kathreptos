"""Syntax and critical-control smoke checks for static community intake pages."""
from html.parser import HTMLParser
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = not dict(attrs).get("src")
            if self.active:
                self.scripts.append("")
    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False
    def handle_data(self, data):
        if self.active:
            self.scripts[-1] += data

for filename, required in {
    "submit.html": ["withdraw_own_community_report", "sanitizePhoto", "flock_community_submissions"],
    "community-review.html": ["list_community_review_queue", "set_community_review_status", "community_report_attachment_paths"],
}.items():
    doc = (ROOT / filename).read_text(encoding="utf-8")
    for marker in required:
        assert marker in doc, (filename, "missing", marker)
    parser = ScriptParser()
    parser.feed(doc)
    assert parser.scripts, filename
    for script in parser.scripts:
        check = subprocess.run(["node", "--check"], input=script, text=True, capture_output=True)
        assert check.returncode == 0, (filename, check.stderr)
    print("Community page JavaScript parsed:", filename)
