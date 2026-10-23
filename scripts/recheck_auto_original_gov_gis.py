"""Revalidate first-party government Flock camera disclosure links daily.

Only a successfully re-fetched, CHANGED original .gov Flock source page with
the formerly exact GIS-layer hyperlink removed can trigger a restricted
database-source revocation. A timeout/redirect/HTTP failure leaves cameras
unchanged but fails the health check, never silently treating an outage
as evidence of cancellation.
"""
import argparse
from collections import Counter

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from corroborate_candidate_government_links import direct_candidate_links
from discover_government_gis_links import fetch_government_page


def source_records():
    origins=fetch_all(api_request,"auto_discovered_government_flock_gis?select=source_key,"
        "government_page_url,original_page_sha256&limit=100","source_key")
    sources=fetch_all(api_request,"trusted_flock_gis_sources?select=source_key,gis_layer_url,"
        "source_status&source_status=eq.verified&limit=100","source_key")
    by_source={s["source_key"]:s for s in sources}
    return [(o,by_source[o["source_key"]]) for o in origins
            if o["source_key"] in by_source]


def original_link_present(document,page,digest,layer):
    matching=direct_candidate_links(document,page,digest,
         "Original government Flock camera disclosure",{layer:{}})
    return any(e["gis_layer_url"]==layer for e in matching)


def run(dry_run=False):
    stats=Counter()
    for src,camera in source_records():
        try:
            page=src["government_page_url"]
            doc,current_sha=fetch_government_page(page)
            stats["official_pages_rechecked"]+=1
            if original_link_present(doc,page,current_sha,camera["gis_layer_url"]):
                stats["still_linked"]+=1
                continue
            if current_sha==src["original_page_sha256"]:
                raise ValueError("Original document unchanged but Flock camera GIS link missing")
            stats["link_removed"]+=1
            if dry_run:continue
            result=api_request("rpc/revoke_auto_gov_flock_source_after_link_loss",
                 method="POST",payload={"p_source_key":src["source_key"],
                                        "p_current_page_sha256":current_sha})
            if result is not True:raise ValueError("Government source withdrawal not confirmed")
            stats["sources_revoked"]+=1
            print("Previously verified .gov Flock source withdrawn:",src["source_key"])
        except Exception as exc:
            stats["errors"]+=1
            print("Government-owned GIS recheck failed:",
                  src.get("source_key"),type(exc).__name__,str(exc)[:200])
    for name in ("official_pages_rechecked","still_linked","link_removed",
                 "sources_revoked","errors"):
        print("Original government GIS recheck",name+":",stats[name])
    return stats


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    result=run(a.parse_args().dry_run)
    if result["errors"]:raise SystemExit("Original-government GIS source recheck incomplete")
