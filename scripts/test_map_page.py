"""Map-first website must not imply that unverified cameras or plate reads are real."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Parse(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.sources = set()
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if 'id' in d:
            self.ids.add(d['id'])
        if tag == 'script' and 'src' in d:
            self.sources.add(d['src'])


class MapPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')
        cls.script = (ROOT / 'map.js').read_text(encoding='utf-8')
        cls.css = (ROOT / 'map.css').read_text(encoding='utf-8')
        p = Parse()
        p.feed(cls.html)
        cls.ids = p.ids
        cls.src = p.sources

    def test_map_first_interface_with_route_fields(self):
        self.assertTrue({'map','routeForm','from','to','hypothetical',
                         'coverageStatus','timelineEvents','play'}.issubset(self.ids))
        self.assertIn('./map.js',self.src)
        self.assertIn('./route-geometry.js',self.src)
        self.assertTrue({'mapSearch','mapSearchForm','jurisdictionFilter',
                         'cameraTextFilter','filterStatus'}.issubset(self.ids))
        self.assertIn('flock_camera_evidence_history',self.script)
        self.assertTrue({'programSearch','programList','programStatus'}.issubset(self.ids))
        self.assertIn('flock_documented_programs',self.script)
        self.assertIn('flock_public_coverage_stats',self.script)
        self.assertIn('flock_public_state_evidence_index',self.script)
        self.assertIn('dated_program_records',self.script)
        self.assertIn('terminated_program_records',self.script)
        self.assertTrue({'stateEvidenceList','stateEvidenceStatus'}.issubset(self.ids))
        self.assertIn('verified_flock_agenda_mentions',self.script)
        self.assertTrue({'agendaMapSearch','agendaMapList','agendaMapStatus'}.issubset(self.ids))
        self.assertIn('nationalStats',self.ids)
        self.assertIn('flock_documented_coverage_areas',self.script)
        self.assertIn('officialAreaPopup',self.script)
        self.assertIn('function sourceFreshness(record)',self.script)
        self.assertIn('sourceNote',self.script)
        self.assertIn('camera location may be outdated',self.script)
        self.assertIn('Original-source check: OVERDUE',self.script)
        self.assertIn('government-endorsed EXTERNAL ArcGIS point',self.script)
        self.assertIn('government-operated GIS point',self.script)
        self.assertIn('./config.js',self.src)
        self.assertIn('./map.css',self.html)

    def test_nationwide_not_six_city_only(self):
        self.assertNotIn('Metropolitan area',self.html)
        self.assertNotIn('All camera locations are fictional',self.html)
        self.assertIn('Nationwide',self.html)
        self.assertIn('flock_camera_locations',self.script)
        self.assertIn('compareRouteChoices(request)',self.script)
        self.assertIn('state.routeRecords',self.script)
        self.assertIn('Geo.closestOnRoute',self.script)
        self.assertIn('verification_status: \'eq.verified\'',self.script)

    def test_no_faked_road_routes_or_default_hypothetical_pins(self):
        verifier=(ROOT/'routing-routes.js').read_text(encoding='utf-8')
        self.assertIn("data?.code !== 'Ok'",verifier)
        self.assertIn('Routing.readAlternatives',self.script)
        self.assertIn('providerBase(CFG.routingServiceBase',self.script)
        self.assertIn('providerBase(CFG.geocodingServiceBase',self.script)
        transport=(ROOT/'routing-provider.js').read_text(encoding='utf-8')
        self.assertIn("cache:'no-store'",transport)
        self.assertIn("referrerPolicy:'no-referrer'",transport)
        self.assertIn("redirect:'error'",transport)
        self.assertIn("state.routeProviderAbort?.abort()",self.script)
        self.assertIn("No straight-line route or guessed detections",self.script)
        self.assertIn("if ($('hypothetical').checked)",self.script)
        self.assertNotIn("SYNTH-4827",self.html)
        self.assertNotIn("simCamera",self.script)

    def test_source_links_use_safe_dom(self):
        self.assertIn("popupFor(record)",self.script)
        self.assertIn('id="showProvisional"',self.html)
        self.assertIn('id="provisionalCount"',self.html)
        self.assertIn('flock_public_tiered_camera_points',self.script)
        self.assertIn("evidence_tier==='government_verified'",self.script)
        self.assertIn("row.evidence_tier==='government_verified'",self.script)
        self.assertIn("record.evidence_tier==='independently_corroborated'",self.script)
        self.assertIn('OFF by default', (ROOT/'methodology.html').read_text(encoding='utf-8'))
        self.assertIn("element.textContent = txt",self.script)
        self.assertIn("noopener noreferrer",self.script)
        self.assertNotIn('.innerHTML',self.script)

    def test_legacy_simulator_retained(self):
        old=(ROOT/'legacy-simulator.html').read_text(encoding='utf-8')
        self.assertIn('SYNTH-4827',old)
        self.assertIn('Synthetic',old)
        self.assertIn('ORIGINAL SIMULATOR',self.html)

    def test_route_alternatives_accessible_and_explicitly_modeled(self):
        self.assertIn('id="routeChoice"',self.html)
        self.assertIn('id="routeChoiceStatus"',self.html)
        self.assertIn('routing-routes.js',self.html)
        self.assertIn('alternatives=true',self.script)
        self.assertIn('Routing.readAlternatives',self.script)
        self.assertIn('state.evidenceAbort?.abort()',self.script)
        self.assertIn('routeCameraRows(box,signal)',self.script)
        self.assertIn("if(state.route===route)displaySelectedRouteEvidence()",self.script)
        self.assertIn('id="providerStatus"',self.html)
        self.assertIn('routing-provider.js',self.html)
        self.assertIn('geoapify-adapter.js',self.html)
        self.assertIn("CFG.locationProvider==='geoapify'",self.script)
        self.assertIn('geoapifyPublicKey', (ROOT/'config.js').read_text(encoding='utf-8'))
        self.assertIn('id="routeComparisonList"',self.html)
        self.assertIn('id="fromMatch"',self.html)
        self.assertIn('id="toMatch"',self.html)
        self.assertIn("resolveRoutePlace('from',from,providerController.signal)",self.script)
        self.assertIn("resolveRoutePlace('to',to,providerController.signal)",self.script)
        self.assertIn('No location was guessed',self.script)
        self.assertIn('id="comparisonStatus"',self.html)
        self.assertIn('route-comparison.js',self.html)
        self.assertIn("outcome={status:'unavailable'",self.script)
        self.assertIn("state.routeComparisons[index]=outcome",self.script)


if __name__=='__main__':
    unittest.main()
