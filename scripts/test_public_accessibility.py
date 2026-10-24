"""Static accessibility checks for core Katoptron navigation and evidence screens.

This intentionally does NOT claim WCAG or screen reader conformance. Browser
and assistive-technology testing is a separate release acceptance requirement.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAGES=["index.html","records.html","accountability.html","analytics.html",
       "submit.html","community-review.html","privacy.html","methodology.html"]

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
        self.duplicates=set()
        self.has_main=False
        self.has_skip=False
        self.lang=False
        self.stylesheet=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        ident=a.get("id")
        if ident:
            if ident in self.ids:self.duplicates.add(ident)
            self.ids.add(ident)
        if tag=="html" and a.get("lang")=="en":self.lang=True
        if tag=="main" and ident=="main-content":self.has_main=True
        if tag=="a" and a.get("class","").find("skip-link")>=0 and a.get("href")=="#main-content":self.has_skip=True
        if tag=="link" and a.get("href")=="./a11y.css":self.stylesheet=True

class AccessibilityShellTests(unittest.TestCase):
    def test_common_keyboard_navigation(self):
        for name in PAGES:
            with self.subTest(page=name):
                parser=Page()
                parser.feed((ROOT/name).read_text(encoding="utf8"))
                self.assertTrue(parser.lang)
                self.assertTrue(parser.has_main)
                self.assertTrue(parser.has_skip)
                self.assertTrue(parser.stylesheet)
                self.assertEqual(parser.duplicates,set())
    def test_evidence_labeling(self):
        for name,phrases in {
            "analytics.html":["unknown","source-dated","not deployment","id=\"stateRows\""],
            "accountability.html":["not proof","Original evidence","role=\"tablist\""],
            "index.html":["unknown coverage","aria-label=\"Main navigation\""],
        }.items():
            source=(ROOT/name).read_text(encoding="utf8").lower()
            for phrase in phrases:
                with self.subTest(page=name,phrase=phrase):
                    self.assertIn(phrase.lower(),source)

if __name__=="__main__":unittest.main()
