"""Recheck original-government endorsements for externally hosted ArcGIS Flock GIS.

A transient unreachable government page is an ERROR, not evidence that a
Flock source was withdrawn. On a successfully retrieved, CHANGED original
government page with the formerly direct endorsed GIS hyperlink removed,
the narrowly scoped database RPC revokes the source and its public camera
records. All other sources remain untouched.
"""
import argparse
import urllib.parse
from collections import Counter

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from corroborate_candidate_government_links import direct_candidate_links
from discover_government_gis_links import fetch_government_page


def approved_external():
    rows=fetch_all(api_request,"official_external_flock_gis_authorities?select=source_key,"
       "parent_source_key,government_disclosure_url,gis_layer_url,"
       "original_page_sha256,government_link_method,verification_status"
       "&verification_status=eq.verified&limit=100","source_key")
    return rows


def check(endorsement,document,page_sha):
    url=endorsement["gis_layer_url"]
    disclosure=endorsement["government_disclosure_url"]
    # The registered government disclosure was already bound to a verified
    # official parent. Never infer another source or domain from a GIS item.
    found=direct_candidate_links(document,disclosure,page_sha,
        "Officially documented Flock program",{url:{"layer_name":"Flock Cameras"}})
    method=endorsement.get("government_link_method") or "government_page_direct_anchor_v1"
    return any(x["gis_layer_url"]==url and x["discovery_method"]==method
               for x in found)


def run(dry_run=False):
    counts=Counter()
    for record in approved_external():
        url=record["government_disclosure_url"]
        try:
            page,page_sha=fetch_government_page(url)
            counts["checked"]+=1
            if check(record,page,page_sha):
                counts["still_linked"]+=1
                continue
            if page_sha==record["original_page_sha256"]:
                raise ValueError("Original government page unchanged but endorsed hyperlink missing")
            counts["removed_from_original_source"]+=1
            if dry_run:continue
            ok=api_request("rpc/revoke_external_flock_endorsement_after_link_loss",
                 method="POST",payload={"p_source_key":record["source_key"],
                                        "p_current_page_sha256":page_sha})
            if ok is not True:
                raise ValueError("Revocation not confirmed by database")
            counts["revoked"]+=1
            print("Original government endorsement withdrawn:",record["source_key"],
                  urllib.parse.urlsplit(url).hostname)
        except Exception as err:
            counts["errors"]+=1
            print("Original government external Flock check failed:",
                  record.get("source_key"),type(err).__name__,str(err)[:200])
    for key in ("checked","still_linked","removed_from_original_source",
                "revoked","errors"):
        print("Government external link recheck",key+":",counts[key])
    return counts


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    result=run(a.parse_args().dry_run)
    if result["errors"]:raise SystemExit("Original government external Flock links need investigation")
