from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"infra"/"routing-gateway"
class GatewayContract(unittest.TestCase):
    def test_no_route_logs_and_no_open_proxy(self):
        c=(ROOT/"default.conf.template").read_text()
        self.assertIn("access_log off;",c)
        self.assertIn("error_log /dev/stderr crit;",c)
        self.assertIn("location ^~ /route/v1/driving/",c)
        self.assertIn("location ^~ /api/",c)
        self.assertIn("location / { return 404; }",c)
        self.assertIn("limit_req zone=routing",c)
        self.assertIn("limit_req zone=geocoding",c)
        self.assertIn('if ($http_origin != "https://ayeemecee0.github.io")',c)
        self.assertIn('proxy_set_header Cookie "";',c)
        self.assertIn('proxy_set_header Referer "";',c)
    def test_mandatory_private_upstream(self):
        c=(ROOT/"docker-compose.yml").read_text()
        self.assertIn("ROUTING_UPSTREAM: ",c)
        self.assertIn("GEOCODING_UPSTREAM: ",c)
        self.assertIn("127.0.0.1:8088:8080",c)
        self.assertIn("read_only: true",c)
    def test_config_not_a_demo_or_secret(self):
        env=(ROOT/".env.example").read_text()
        self.assertNotIn("api_key=",env)
        self.assertNotIn("photon.komoot.io",env)
        self.assertNotIn("router.project-osrm.org",env)
if __name__=="__main__":unittest.main()
