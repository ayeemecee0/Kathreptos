"""Automatically register truly first-party Flock camera GIS source on county server.

Original source evidence must pass audit_agency_hosted_gis.inspect() at the
moment of attestation. The data path bypasses the need for an exact Flock layer
anchor on a city webpage; it DOES NOT bypass original government publisher
domain, original Flock layer metadata, complete stable feature-ID or geometry,
duplicate and database security verification. Private candidate first.
"""
import argparse
from collections import Counter

from audit_agency_hosted_gis import SOURCES, inspect
from discover_camera_gis_sources import stage_candidate
from auto_verify_flock_agenda import api_request
from auto_verify_camera_profiles import sync as refresh_verified

SOURCE_KEY='agency_alachua_fl'

def run(dry_run=False,publish=False):
    metrics=Counter()
    for source in SOURCES:
        try:
            verified=inspect(source,include_private_locations=True)
            original_points=verified.pop('_private_locations')
            if len(original_points)!=verified['point_count']:
                raise ValueError('Camera coordinate payload differs from full original GIS inventory')
            metrics['qualified_sources']+=1
            metrics['qualified_source_points']+=len(original_points)
            if dry_run:
                continue
            # Staging is a PRIVATE ledger operation, not automatic publication.
            stage_candidate({
              'gis_layer_url':verified['layer_url'],
              'layer_name':verified['layer_name'],
              'geometry_type':'esriGeometryPoint',
              'object_id_field':verified['object_id_field'],
              'public_gov_context_url':source['original_gis_page'],
              'trust_status':'unverified',
              'layer_purpose':(
                'Original agency GIS independently authenticated by live same-domain '
                'government GIS webpage/portal; service and Flock layer identity and '
                'stable complete point IDs confirmed twice. No proof of current uptime.'
              ),
            })
            metrics['private_candidates_staged']+=1
            result=api_request('rpc/register_first_party_agency_flock_source',
                 method='POST',payload={
                   'p_source_key':SOURCE_KEY,
                   'p_page_sha256':verified['original_page_sha256'],
                   'p_layer_sha256':verified['geometry_sha256'],
                   'p_layer_name':verified['layer_name'],
                   'p_camera_id_field':verified['individual_id_field'],
                   'p_identity_basis':verified['identifier_basis'],
                   'p_locations':original_points,
                 })
            if result is not True:
                raise ValueError('Database did not independently authorize first-party agency source')
            metrics['new_authorities_registered']+=1
        except Exception as exc:
            metrics['held']+=1
            print('First-party agency-source held:',source['jurisdiction'],
                 type(exc).__name__)
    if publish and not dry_run and metrics['new_authorities_registered']:
        totals=refresh_verified()
        metrics['verified_points_published_or_rechecked']=totals.get('published',0)+totals.get('rechecked',0)
        metrics['verification_errors']+=totals.get('errors',0)
    for name in ('qualified_sources','qualified_source_points',
                 'private_candidates_staged','new_authorities_registered',
                 'verified_points_published_or_rechecked','held',
                 'verification_errors'):
        print('ORIGINAL AGENCY GIS',name,metrics[name])
    if metrics['held'] or metrics['verification_errors']:
        raise ValueError('Government GIS registration has unresolved source or publication failure')
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--publish',action='store_true')
    args=p.parse_args()
    run(args.dry_run,args.publish)
