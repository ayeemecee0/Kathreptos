import unittest
from unittest.mock import patch
import auto_verify_camera_profiles as v
S={"source_key":"peoria_az","source_status":"verified",
"gis_layer_url":"https://gis.peoriaaz.gov/arcgis/rest/services/PM/pmPublicWorks/MapServer/286",
"government_evidence_url":"https://devservices.peoriaaz.gov/devservices/Cap/CapHome.aspx?TabName=HOME&module=Planning",
"jurisdiction_label":"Peoria, AZ","expected_id_field":"OBJECTID",
"bounds_south":33.2,"bounds_west":-113,"bounds_north":34.5,"bounds_east":-111.4}
P={"source_key":"peoria_az","profile_status":"verified","identity_mode":"official_flock_layer",
"vendor_field":None,"camera_id_field":"CameraID",
"expected_layer_name":"Flock Cameras","service_evidence_mode":"listed_flock_layer"}
R={"authority_key":"peoria_az","verification_status":"verified",
"government_gis_host":"gis.peoriaaz.gov","official_government_page":S["government_evidence_url"],
"allowed_layer_path":"/arcgis/rest/services/PM/pmPublicWorks/MapServer/286",
"jurisdiction_label":"Peoria, AZ"}
FIELDS=[{"name":"OBJECTID","type":"esriFieldTypeOID"},{"name":"CameraID","type":"esriFieldTypeString"}]
L={"name":"Flock Cameras","type":"Feature Layer","geometryType":"esriGeometryPoint","fields":FIELDS}
SERVICE={"layers":[{"id":286,"name":"Flock Cameras"}]}
def f(oid=3,lat=33.67,lon=-112.29,tag="P003"):
 return {"attributes":{"OBJECTID":oid,"CameraID":tag},"geometry":{"x":lon,"y":lat}}
class TestProfiles(unittest.TestCase):
 def test_reviewed_root_only(self):
  self.assertTrue(v.authorize(S,P,R))
  with self.assertRaises(ValueError):v.authorize(S,P,None)
  with self.assertRaises(ValueError):v.authorize({**S,"source_status":"candidate"},P,R)
  with self.assertRaises(ValueError):v.authorize({**S,"gis_layer_url":"https://evil.gov/MapServer/1"},P,R)
 def test_authenticated_agency_owned_flock_oid_only_path(self):
  source={**S,'source_key':'agency_alachua_fl',
    'gis_layer_url':'https://maps.alachuacounty.us/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0',
    'government_evidence_url':'https://growth-management.alachuacounty.us/GIS',
    'jurisdiction_label':'Alachua County, FL',
    'bounds_south':29.0,'bounds_north':30.4,
    'bounds_west':-83.5,'bounds_east':-81.9}
  root={**R,'authority_key':'agency_alachua_fl',
    'government_gis_host':'maps.alachuacounty.us',
    'official_government_page':source['government_evidence_url'],
    'allowed_layer_path':'/server/rest/services/Hosted/Flock_Cameras/FeatureServer/0',
    'jurisdiction_label':'Alachua County, FL'}
  policy={**P,'source_key':'agency_alachua_fl','camera_id_field':'OBJECTID'}
  original={'name':'Flock Cameras','type':'Feature Layer',
    'geometryType':'esriGeometryPoint',
    'fields':[{'name':'OBJECTID','type':'esriFieldTypeOID'}]}
  listing={'layers':[{'id':0,'name':'Flock Cameras'}]}
  self.assertTrue(v.authorize(source,policy,root))
  v.check_metadata(source,policy,listing,original)
  rows,held,total=v.verify_points(source,policy,{'features':[
    {'attributes':{'OBJECTID':11},'geometry':{'x':-82.3,'y':29.6}},
    {'attributes':{'OBJECTID':12},'geometry':{'x':-82.32,'y':29.62}},
  ]})
  self.assertEqual((len(rows),total,sum(held.values())),(2,2,0))
  self.assertEqual(rows[0]['source_type'],'official_government')
  with self.assertRaisesRegex(ValueError,'receipt'):
   v.authorize({**source,'source_key':'unverified_external'},
       {**policy,'source_key':'unverified_external'},root)
  with self.assertRaises(ValueError):
   v.verify_points(source,policy,{'features':[
     {'attributes':{'OBJECTID':12.5},'geometry':{'x':-82.3,'y':29.6}},
   ]})
 def test_metadata_requires_original_flock_only_point_layer(self):
  v.check_metadata(S,P,SERVICE,L)
  with self.assertRaises(ValueError):
   v.check_metadata(S,P,SERVICE,{**L,"name":"Traffic Cameras"})
  with self.assertRaises(ValueError):
   v.check_metadata(S,P,{"layers":[]},L)
 def test_identified_points_only(self):
  rows,held,n=v.verify_points(S,P,{"features":[f(),f(4,tag=""),f(5,lon=0)]})
  self.assertEqual((len(rows),n),(1,3))
  self.assertEqual(sum(held.values()),2)
  self.assertEqual(rows[0]["location_accuracy"],"exact")
 def test_duplicate_government_id_not_published(self):
  with self.assertRaises(ValueError):
   v.verify_points(S,P,{"features":[f(),f()]})
 def test_lawrenceville_mixed_school_camera_exclusion(self):
  city={**S,"source_key":"lawrenceville_ga",
        "jurisdiction_label":"Lawrenceville, GA",
        "bounds_south":33.75,"bounds_west":-84.15,
        "bounds_north":34.1,"bounds_east":-83.85}
  policy={**P,"source_key":"lawrenceville_ga","vendor_field":"CameraType"}
  payload={"features":[
    {"attributes":{"OBJECTID":828,"CameraID":"1","CameraType":"PD Flock Camera"},
     "geometry":{"x":-83.97,"y":33.92}},
    {"attributes":{"OBJECTID":829,"CameraID":"2","CameraType":"PD School Camera"},
     "geometry":{"x":-83.99,"y":33.93}}]}
  rows,held,total=v.verify_points(city,policy,payload)
  self.assertEqual((len(rows),total),(1,2))
  self.assertEqual(held["not a Flock camera per original GIS field"],1)
  with self.assertRaises(ValueError):
   v.check_metadata(city,policy,SERVICE,L)
 def test_webster_city_vendor_stated_in_original_service(self):
  city={**S,"source_key":"webster_tx","jurisdiction_label":"Webster, TX"}
  policy={**P,"source_key":"webster_tx","expected_layer_name":"FLOCK Cameras - Webster PD",
          "camera_id_field":"ID","service_evidence_mode":"explicit_flock_service_text"}
  meta={"name":"FLOCK Cameras - Webster PD","type":"Feature Layer",
        "geometryType":"esriGeometryPoint",
        "fields":[{"name":"OBJECTID","type":"esriFieldTypeOID"},
                  {"name":"ID","type":"esriFieldTypeString"}]}
  service={"serviceDescription":"Webster PD Cameras (FLOCK) for reading vehicle license plates"}
  v.check_metadata(city,policy,service,meta)
  with self.assertRaises(ValueError):
   v.check_metadata(city,policy,{"serviceDescription":"Traffic cameras"},meta)
 def test_single_transient_original_government_gis_timeout_recovers(self):
  with (patch.object(v,"get_official_json",side_effect=[TimeoutError("original host slow"),{"features":[]}]) as fetch,
        patch.object(v.time,"sleep") as nap):
   data=v.resilient_government_gis_json("https://government.example.gov/MapServer/1?f=json")
  self.assertEqual(data,{"features":[]})
  self.assertEqual(fetch.call_count,2)
  nap.assert_called_once()
  with (patch.object(v,"get_official_json",side_effect=TimeoutError("source unavailable")),
        patch.object(v.time,"sleep")):
   with self.assertRaises(TimeoutError):
    v.resilient_government_gis_json("https://government.example.gov/MapServer/1?f=json")
 def test_government_endorsed_arcgis_requires_exact_verified_attestation(self):
  external={"source_key":"external_source","parent_source_key":"peoria_az",
    "gis_layer_url":"https://services3.arcgis.com/abcd1234/arcgis/rest/services/Flock_Cameras/FeatureServer/0",
    "government_disclosure_url":S["government_evidence_url"],
    "verification_status":"verified"}
  linked={**S,"source_key":"external_source",
    "gis_layer_url":external["gis_layer_url"]}
  self.assertTrue(v.authorize(linked,{**P,"source_key":"external_source"},None,external))
  with self.assertRaises(ValueError):
   v.authorize(linked,{**P,"source_key":"external_source"},None,
               {**external,"verification_status":"revoked"})
  with self.assertRaises(ValueError):
   v.authorize(linked,{**P,"source_key":"external_source"},None,
               {**external,"gis_layer_url":"https://evil.example/Fake/FeatureServer/1"})
 def test_full_gis_inventory_uses_object_ids_not_silent_page_limit(self):
  identifiers=list(range(1,156))
  ids={"objectIdFieldName":"OBJECTID","objectIds":identifiers}
  def row(i):
   return {"attributes":{"OBJECTID":i,"CameraID":"P"+str(i)},
           "geometry":{"x":-112.2,"y":33.65}}
  with patch.object(v,"resilient_government_gis_json",side_effect=[
      SERVICE,L,ids,{"features":[row(i) for i in identifiers[:150]]},
      {"features":[row(i) for i in identifiers[150:]]},ids]) as fetch:
   data=v.query_gis(S,P)
  self.assertEqual(len(data["features"]),155)
  self.assertEqual(fetch.call_count,6)
  rows,held,total=v.verify_points(S,P,data)
  self.assertEqual((len(rows),total,sum(held.values())),(155,155,0))
 def test_gis_id_pagination_holds_missing_record(self):
  ids={"objectIdFieldName":"OBJECTID","objectIds":[1,2]}
  with patch.object(v,"resilient_government_gis_json",side_effect=[
      SERVICE,L,ids,{"features":[f(oid=1)]}]):
   with self.assertRaisesRegex(ValueError,"omitted/duplicated"):
    v.query_gis(S,P)
 def test_gis_id_snapshot_changes_do_not_publish(self):
  a={"objectIdFieldName":"OBJECTID","objectIds":[1]}
  b={"objectIdFieldName":"OBJECTID","objectIds":[1,2]}
  with patch.object(v,"resilient_government_gis_json",side_effect=[
      SERVICE,L,a,{"features":[f(oid=1)]},b]):
   with self.assertRaisesRegex(ValueError,"changed during"):
    v.query_gis(S,P)
 def test_gis_id_count_over_capacity_fails_before_downloading(self):
  too_many={"objectIdFieldName":"OBJECTID",
            "objectIds":list(range(1,v.MAX_SOURCE_FEATURES+2))}
  with patch.object(v,"resilient_government_gis_json",side_effect=[
      SERVICE,L,too_many]) as fetch:
   with self.assertRaisesRegex(ValueError,"oversized"):
    v.query_gis(S,P)
  self.assertEqual(fetch.call_count,3)
 def test_transient_network_failure_retries_and_recovers(self):
  import urllib.error
  with (patch.object(v,"query_gis",side_effect=[
    urllib.error.URLError("timeout"),{"features":[f()]}]) as query,
    patch.object(v,"time") as sleep):
   rows,held,count=v.source_with_bounded_retries(S,P,attempts=2)
  self.assertEqual(count,1)
  self.assertEqual(query.call_count,2)
 def test_failed_network_retries_do_not_revoke(self):
  import urllib.error
  with (patch.object(v,"query_gis",side_effect=urllib.error.URLError("timeout")),
        patch.object(v,"revoke_stale") as revoke,
        patch.object(v,"time")):
   with self.assertRaises(RuntimeError):
    v.source_with_bounded_retries(S,P,attempts=2)
  revoke.assert_not_called()
 def test_lowercase_original_object_id_but_stable_canonical_record(self):
  city={**S,"source_key":"original_az"}
  fields=[{"name":"objectid","type":"esriFieldTypeOID"},
          {"name":"CameraID","type":"esriFieldTypeString"}]
  original={**L,"fields":fields}
  v.check_metadata(city,P,SERVICE,original)
  self.assertEqual(v.original_object_id_field(fields),"objectid")
  rows,held,total=v.verify_points(city,P,{"features":[{
    "attributes":{"objectid":12,"CameraID":"P012"},
    "geometry":{"x":-112.25,"y":33.67}}]})
  self.assertEqual((len(rows),total),(1,1))
  self.assertEqual(held,{})
  self.assertTrue(rows[0]["record_key"].startswith("gis-original_az-12-"))
 def test_original_city_police_flock_unit_locations_with_noncanonical_oid(self):
  approved={**S,"source_key":"newport_beach_ca",
    "gis_layer_url":"https://nbgis.newportbeachca.gov/arcgis/rest/services/EmployeeMasterMap/MapServer/299",
    "government_evidence_url":"https://nbgis.newportbeachca.gov/Geocortex/Essentials/REST/sites/NewportGIS/map/mapservices/7",
    "jurisdiction_label":"Newport Beach, CA",
    "expected_id_field":"OBJECTID_12",
    "bounds_south":33.52,"bounds_north":33.77,
    "bounds_west":-117.98,"bounds_east":-117.69}
  policy={**P,"source_key":"newport_beach_ca",
    "camera_id_field":"FlockUnitNo","expected_layer_name":"Flock Unit Locations",
    "service_evidence_mode":"listed_flock_layer"}
  root={**R,"authority_key":"newport_beach_ca",
    "government_gis_host":"nbgis.newportbeachca.gov",
    "official_government_page":approved["government_evidence_url"],
    "allowed_layer_path":"/arcgis/rest/services/EmployeeMasterMap/MapServer/299",
    "jurisdiction_label":"Newport Beach, CA"}
  self.assertTrue(v.authorize(approved,policy,root))
  with self.assertRaises(ValueError):
   v.authorize(approved,policy,None)
  self.assertEqual(v.original_object_id_field([
    {"name":"OBJECTID_12","type":"esriFieldTypeOID"}]),"OBJECTID_12")
  layer={"name":"Flock Unit Locations","type":"Feature Layer",
         "geometryType":"esriGeometryPoint",
         "fields":[{"name":"OBJECTID_12","type":"esriFieldTypeOID"},
                   {"name":"FlockUnitNo","type":"esriFieldTypeString"}]}
  v.check_metadata(approved,policy,{"layers":[{"id":299,"name":"Flock Unit Locations"}]},layer)
  rows,held,n=v.verify_points(approved,policy,{"features":[
   {"attributes":{"OBJECTID_12":901,"FlockUnitNo":"NB-01"},
    "geometry":{"x":-117.85,"y":33.62}}]})
  self.assertEqual((len(rows),n,dict(held)),(1,1,{}))
  self.assertIn("city Police GIS",rows[0]["evidence_summary"])
  self.assertEqual(rows[0]["location_accuracy"],"exact")
 def test_permit_only_points_are_not_individually_verified_cameras(self):
  permit_fields=[{"name":"objectid","type":"esriFieldTypeOID"},
                 {"name":"permitno","type":"esriFieldTypeString"}]
  with self.assertRaisesRegex(ValueError,"identifier"):
   v.check_metadata(S,P,SERVICE,{**L,"fields":permit_fields})
 def test_shard_partition_is_exhaustive_and_disjoint(self):
  keys=["elpaso_co","monroe_wa","peoria_az","lawrenceville_ga","webster_tx",
        "ext_government_city_1","autogov_georgiatown2","gis_county_lpar_1"]
  for key in keys:
   self.assertEqual(sum(v.assigned_to_verification_shard(key,i,4)
                        for i in range(4)),1)
   self.assertTrue(v.assigned_to_verification_shard(key,0,1))
  for bad in ((-1,4),(4,4),(0,0),(0,17)):
   with self.assertRaises(ValueError):
    v.assigned_to_verification_shard("peoria_az",*bad)
 def test_sharded_worker_processes_only_its_sources(self):
  keys=["elpaso_co","monroe_wa","peoria_az","lawrenceville_ga","webster_tx"]
  shard=next(i for i in range(4)
             if 0<sum(v.assigned_to_verification_shard(k,i,4) for k in keys)<len(keys))
  items=[({**S,"source_key":key},P) for key in keys]
  with (patch.object(v,"approved_sources",return_value=items),
        patch.object(v,"source_with_bounded_retries",
                     return_value=([{"record_key":"gis-test-1"}],{},1)) as read,
        patch.object(v,"write_verified") as write):
   outcome=v.sync(dry_run=True,shard=shard,shards=4)
  self.assertEqual(outcome["sources_checked"],
       sum(v.assigned_to_verification_shard(k,shard,4) for k in keys))
  self.assertEqual(read.call_count,outcome["sources_checked"])
  write.assert_not_called()
 def test_existing_verification_inventory_is_paged_beyond_1000(self):
  original=[{"record_key":"gis-peoria_az-"+str(i)+"-abc",
             "verification_status":"verified"} for i in range(1101)]
  pages=[original[i:i+50] for i in range(0,len(original),50)]
  with patch.object(v,"api_request",side_effect=pages) as req:
   rows=v.fetch_existing("gis-peoria_az-")
  self.assertEqual(len(rows),1101)
  self.assertGreater(req.call_count,20)
 def test_reconciliation_scopes_literal_underscores_to_exact_source(self):
  from urllib.parse import urlsplit,parse_qs
  valid=[{"record_key":"gis-peoria_az-1-deadbeef","verification_status":"verified"}]
  with patch.object(v,"api_request",side_effect=[valid]) as req:
   self.assertEqual(v.fetch_existing("gis-peoria_az-"),valid)
  query=parse_qs(urlsplit(req.call_args.args[0]).query)
  self.assertIn(r"\_",query["record_key"][0])
  wrong=[{"record_key":"gis-peoriaXaz-1-deadbeef","verification_status":"verified"}]
  with patch.object(v,"api_request",side_effect=[wrong]):
   with self.assertRaisesRegex(ValueError,"source boundary"):
    v.fetch_existing("gis-peoria_az-")
 def test_sudden_mass_camera_removal_blocks_before_writes(self):
  old=[{"record_key":"gis-test-"+str(i)+"-abc"} for i in range(20)]
  keys={x["record_key"] for x in old[:14]}
  with self.assertRaisesRegex(ValueError,"Unexpectedly large"):
   v.validate_reconciliation_delta(old,keys)
  missing=v.validate_reconciliation_delta(old,{x["record_key"] for x in old[:18]})
  self.assertEqual(missing,{x["record_key"] for x in old[18:]})
 def test_paged_existing_source_query_is_restricted(self):
  for prefix in ("anything*","gis-../other-"):
   with self.assertRaises(ValueError):v.fetch_existing(prefix)
 def test_duplicate_existing_record_ids_fail_before_writes(self):
  with self.assertRaises(ValueError):
   v.validate_reconciliation_delta([{"record_key":"a"},{"record_key":"a"}],{"a"})
 def test_camera_withdrawal_requires_time_separated_backend_confirmation(self):
  missing={"gis-peoria_az-7-aaa"}
  with patch.object(v,"api_request",return_value={
    "confirmed":[],"pending":1}) as rpc:
   confirmed,pending=v.confirm_time_separated_withdrawals("peoria_az",missing)
  self.assertEqual((confirmed,pending),(set(),1))
  self.assertEqual(rpc.call_args.args[0],"rpc/confirm_gis_camera_withdrawals")
  self.assertEqual(rpc.call_args.kwargs["payload"]["p_missing_keys"],sorted(missing))
  with patch.object(v,"api_request",return_value={
    "confirmed":["gis-peoria_az-7-aaa"],"pending":0}):
   confirmed,pending=v.confirm_time_separated_withdrawals("peoria_az",missing)
  self.assertEqual((confirmed,pending),(missing,0))
 def test_camera_reappeared_discards_previous_missing_hold(self):
  with patch.object(v,"api_request",return_value={
    "confirmed":[],"pending":0}) as rpc:
   self.assertEqual(v.confirm_time_separated_withdrawals("peoria_az",set()),
                    (set(),0))
  self.assertEqual(rpc.call_args.kwargs["payload"]["p_missing_keys"],[])
 def test_backend_withdrawal_cannot_touch_another_camera_source(self):
  with patch.object(v,"api_request") as rpc:
   with self.assertRaises(ValueError):
    v.confirm_time_separated_withdrawals(
      "peoria_az",{"gis-monroe_wa-1-abc"})
  rpc.assert_not_called()
 def test_database_withdrawal_receipt_cannot_claim_unobserved_camera(self):
  missing={"gis-peoria_az-2-a"}
  for bad in ({"confirmed":["gis-peoria_az-99-a"],"pending":0},
              {"confirmed":[*missing],"pending":1},
              {"confirmed":list(missing)*2,"pending":0},
              {"confirmed":[],"pending":-1},
              None):
   with patch.object(v,"api_request",return_value=bad):
    with self.assertRaises(ValueError):
     v.confirm_time_separated_withdrawals("peoria_az",missing)
 def test_sync_never_immediately_withdraws_small_missing_snapshot(self):
  source={**S,"source_key":"peoria_az"}
  present={"record_key":"gis-peoria_az-10-a"}
  removed={"record_key":"gis-peoria_az-11-b"}
  with (patch.object(v,"approved_sources",return_value=[(source,P)]),
        patch.object(v,"source_with_bounded_retries",return_value=([present],{},1)),
        patch.object(v,"fetch_existing",return_value=[present,removed]),
        patch.object(v,"confirm_time_separated_withdrawals",
                     return_value=(set(),1)) as confirm,
        patch.object(v,"publish_verified_batches",return_value=v.Counter()) as save):
   result=v.sync()
  self.assertEqual(result["pending_withdrawal"],1)
  self.assertEqual(result["withdrawn"],0)
  confirm.assert_called_once_with("peoria_az",{removed["record_key"]})
  self.assertEqual(save.call_args.args[1],set())

 def test_batched_camera_publish_verifies_exact_receipts(self):
  new={"record_key":"gis-peoria_az-1-a","source_type":"official_government"}
  old={"record_key":"gis-peoria_az-2-b","source_type":"official_government"}
  lost={"gis-peoria_az-3-c"}
  seen=[]
  def db(path,method="GET",payload=None,prefer=None):
   seen.append((path,method,payload,prefer))
   if method=="POST": return [{"record_key":new["record_key"]}]
   if payload.get("verification_status")=="revoked":
    return [{"record_key":"gis-peoria_az-3-c"}]
   return [{"record_key":old["record_key"]}]
  with patch.object(v,"api_request",side_effect=db):
   result=v.publish_verified_batches([new,old],lost)
  self.assertEqual((result["published"],result["rechecked"],result["withdrawn"]),(1,1,1))
  self.assertEqual([x[1] for x in seen],["POST","PATCH","PATCH"])
  self.assertTrue(all("select=record_key" in x[0] for x in seen))
 def test_batch_fails_if_existing_verified_camera_not_updated(self):
  rows=[{"record_key":"gis-peoria_az-1-a"}]
  with patch.object(v,"api_request",side_effect=[[],[]]):
   with self.assertRaisesRegex(ValueError,"skipped"):
    v.publish_verified_batches(rows,set())
 def test_batch_fails_on_conflicting_evidence_keys(self):
  with patch.object(v,"api_request") as write:
   for rows,revoked in (
       ([{"record_key":"gis-peoria_az-1-a"}]*2,set()),
       ([{"record_key":"gis-peoria_az-1-a"}],{"gis-peoria_az-1-a"}),
       ([{"record_key":"not-official"}],set())
   ):
    with self.assertRaises(ValueError):
     v.publish_verified_batches(rows,revoked)
   write.assert_not_called()
 def test_batch_withdrawal_requires_exact_receipt(self):
  rows=[{"record_key":"gis-peoria_az-1-a"}]
  with patch.object(v,"api_request",side_effect=[
      [{"record_key":"gis-peoria_az-1-a"}],[]]):
   with self.assertRaisesRegex(ValueError,"withdrawal receipt"):
    v.publish_verified_batches(rows,{"gis-peoria_az-2-b"})
 def test_dryrun_never_writes(self):
  with (patch.object(v,"approved_sources",return_value=[(S,P)]),
        patch.object(v,"query_gis",return_value={"features":[f()]}),
        patch.object(v,"write_verified") as save):
   result=v.sync(dry_run=True)
  self.assertEqual(result["eligible"],1)
  save.assert_not_called()
if __name__=="__main__":unittest.main()
