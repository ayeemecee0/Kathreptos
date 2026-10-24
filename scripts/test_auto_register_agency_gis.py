import unittest
from unittest.mock import patch
import auto_register_agency_gis as a

SOURCE=a.SOURCE_KEY
proof={
  'layer_url':'https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0',
  'layer_name':'Flock Cameras','point_count':2,
  'object_id_field':'OBJECTID','individual_id_field':'OBJECTID',
  'identifier_basis':'arcgis_typed_objectid',
  'original_page_sha256':'a'*64,'geometry_sha256':'b'*64,
  '_private_locations':[{'id':1,'lat':29.6,'lon':-82.3},
                        {'id':2,'lat':29.61,'lon':-82.32}],
}
class Register(unittest.TestCase):
 def test_dryrun_verifies_without_database_request(self):
  with (patch.object(a,'inspect',return_value=dict(proof)) as probe,
        patch.object(a,'api_request') as api,
        patch.object(a,'stage_candidate') as stage):
   r=a.run(dry_run=True)
  self.assertEqual(r['qualified_source_points'],2)
  probe.assert_called_once()
  self.assertTrue(probe.call_args.kwargs['include_private_locations'])
  api.assert_not_called();stage.assert_not_called()
 def test_qualified_first_party_source_cannot_skip_private_staging(self):
  with (patch.object(a,'inspect',return_value=dict(proof)),
        patch.object(a,'api_request',side_effect=[[],True]) as api,
        patch.object(a,'stage_candidate') as stage):
   r=a.run()
  self.assertEqual(r['new_authorities_registered'],1)
  row=stage.call_args.args[0]
  self.assertEqual(row['trust_status'],'unverified')
  self.assertNotIn('latitude',row)
  self.assertNotIn('longitude',row)
  self.assertEqual(api.call_args.kwargs['payload']['p_locations'],proof['_private_locations'])
  self.assertEqual(api.call_args.kwargs['payload']['p_source_key'],SOURCE)
 def test_rechecks_existing_authority_without_duplicate_registration(self):
  with (patch.object(a,'inspect',return_value=dict(proof)),
        patch.object(a,'api_request',return_value=[{
          'source_key':SOURCE,'gis_layer_url':proof['layer_url'],
          'source_status':'verified'}]) as api,
        patch.object(a,'stage_candidate') as stage):
   r=a.run()
  self.assertEqual(r['existing_authorities_revalidated'],1)
  self.assertEqual(api.call_count,1)
  stage.assert_not_called()
 def test_revoked_source_cannot_be_reapproved_automatically(self):
  for status in ('revoked','candidate'):
   with (patch.object(a,'inspect',return_value=dict(proof)),
         patch.object(a,'api_request',return_value=[{
           'source_key':SOURCE,'gis_layer_url':proof['layer_url'],
           'source_status':status}]),
         patch.object(a,'stage_candidate') as stage):
    with self.assertRaisesRegex(ValueError,'unresolved'):
     a.run()
   stage.assert_not_called()
 def test_automatic_refresh_only_after_new_authority_registration(self):
  with (patch.object(a,'inspect',return_value=dict(proof)),
        patch.object(a,'api_request',side_effect=[[],True]),
        patch.object(a,'stage_candidate'),
        patch.object(a,'refresh_verified',return_value={'published':2,'rechecked':0,'errors':0}) as sync):
   r=a.run(publish=True)
  self.assertEqual(r['verified_points_published_or_rechecked'],2)
  sync.assert_called_once()

if __name__=='__main__':unittest.main()
