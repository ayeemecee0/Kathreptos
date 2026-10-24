from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class RenderBlueprintSafety(unittest.TestCase):
 def test_blueprint_is_opt_in_and_needs_upstream_configuration(self):
  y=(ROOT/'render.yaml').read_text()
  self.assertIn('name: katoptron-routing-gateway',y)
  self.assertIn('runtime: docker',y)
  self.assertIn('autoDeploy: false',y)
  self.assertIn('plan: starter',y)
  self.assertIn('healthCheckPath: /healthz',y)
  self.assertIn('dockerfilePath: ./infra/routing-gateway/Dockerfile',y)
  self.assertIn('key: ROUTING_UPSTREAM\n        sync: false',y)
  self.assertIn('key: GEOCODING_UPSTREAM\n        sync: false',y)
  self.assertNotIn('router.project-osrm.org',y)
  self.assertNotIn('photon.komoot.io',y)

if __name__=='__main__':unittest.main()
