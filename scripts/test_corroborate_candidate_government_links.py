import unittest
from unittest.mock import patch
from discover_government_gis_links import Anchors
import corroborate_candidate_government_links as c

PAGE="https://city.example.gov/flock"
GIS="https://services.arcgis.com/ABC0001/arcgis/rest/services/Flock_Cameras/FeatureServer/0"
def html(source):
 doc=Anchors();doc.feed(source);return doc
class Links(unittest.TestCase):
 def test_direct_original_government_link_is_private_receipt(self):
  doc=html('<h1>City Flock Safety ALPR camera program</h1>'
           '<a href="'+GIS+'">View GIS Flock cameras</a>')
  rows=c.direct_candidate_links(doc,PAGE,'a'*64,"City Example, ST",{GIS:{"layer_name":"Flock Cameras"}})
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["government_page_sha256"],'a'*64)
  self.assertEqual(rows[0]["layer_metadata_status"],"unverified")
 def test_unrelated_government_page_does_not_claim_ownership(self):
  doc=html('<h1>Maps and parking</h1><a href="'+GIS+'">Other</a>')
  self.assertFalse(c.direct_candidate_links(doc,PAGE,'a'*64,"City Example, ST",{GIS:{}}))
 def test_mentioned_layer_not_linked_is_no_proof(self):
  doc=html('<h1>Flock Safety cameras</h1><a href="/gis">Map here</a>')
  self.assertFalse(c.direct_candidate_links(doc,PAGE,'a'*64,"City Example, ST",{GIS:{}}))
 def test_mismatched_arcgis_url_is_no_proof(self):
  doc=html('<h1>Flock Safety cameras</h1><a href="'+GIS[:-1]+'1">GIS map</a>')
  self.assertFalse(c.direct_candidate_links(doc,PAGE,'a'*64,"City Example, ST",{GIS:{}}))
 def test_dry_run_no_database_writes(self):
  doc=html('<h1>Flock Safety camera program</h1><a href="'+GIS+'">Flock GIS map</a>')
  with (patch.object(c,"candidates",return_value={GIS:{}}),
        patch.object(c,"authoritative_page_seeds",return_value={PAGE:"City Example, ST"}),
        patch.object(c,"fetch_government_page",return_value=(doc,'a'*64)),
        patch.object(c,"stage") as stage):
   result=c.run(dry_run=True)
  self.assertEqual(result["exact_government_links"],1)
  stage.assert_not_called()
 def test_government_service_directory_unique_layer_is_private_receipt(self):
  service=GIS.rsplit("/",1)[0]
  doc=html('<h1>Flock Safety camera program</h1><a href="'+service+'">Flock camera GIS</a>')
  rows=c.direct_candidate_links(doc,PAGE,'b'*64,"City Example, ST",
    {GIS:{"layer_name":"Flock Cameras"}})
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["gis_layer_url"],GIS)
  self.assertEqual(rows[0]["discovery_method"],"government_page_direct_service_v1")
  self.assertEqual(rows[0]["layer_metadata_status"],"unverified")
 def test_service_link_with_multiple_candidate_layers_is_not_specific_proof(self):
  service=GIS.rsplit("/",1)[0]
  doc=html('<h1>Flock Safety cameras</h1><a href="'+service+'">Flock GIS</a>')
  self.assertEqual(c.direct_candidate_links(doc,PAGE,'c'*64,"City Example, ST",{
    GIS:{"layer_name":"Flock Cameras"},
    service+"/1":{"layer_name":"Flock Cameras"}
  }),[])
 def test_no_direct_promotion(self):
  with patch.object(c,"api_request",return_value=None) as api:
   c.stage([{"gis_layer_url":GIS}])
  self.assertIn("government_gis_disclosure_leads",api.call_args.args[0])
  self.assertNotIn("trusted_flock_gis_sources",api.call_args.args[0])
  self.assertNotIn("flock_camera_locations",api.call_args.args[0])
if __name__=="__main__":
 unittest.main()
