"""Correlate unverified Flock GIS layers with exact original-government links.

A public Flock-labelled ArcGIS layer is NOT government-authenticated. Check
that an independently sourced original-government Flock disclosure actually
links to that exact GIS layer. Only then store a PRIVATE government-page
hyperlink receipt. A receipt is not a verified source root and never publishes
camera coordinates. Neither ArcGIS ownership names nor adjacent map pages
count as ownership evidence.
"""
import argparse
from collections import Counter
import urllib.parse

from auto_verify_flock_agenda import api_request
from paged_supabase import fetch_all
from discover_government_gis_links import (
    LINK_LABEL, fetch_government_page, normalized_url, original_camera_disclosure
)
from government_domain_registry import valid_https_url

MAX_CANDIDATES=130
MAX_SEEDS=3000


def candidates():
    rows=fetch_all(api_request,"flock_gis_source_candidates?select=gis_layer_url,"
        "layer_name,trust_status&trust_status=eq.unverified&limit=130","gis_layer_url")
    # The entire private candidate registry is read with bounded pagination.
    result={}
    for row in rows:
        url=normalized_url(row.get("gis_layer_url") or "")
        parsed=valid_https_url(url) if url else None
        if (url and parsed and parsed.query=="" and parsed.fragment==""
            and ("/FeatureServer/" in parsed.path or "/MapServer/" in parsed.path)
            and parsed.path.rsplit("/",1)[1].isdigit()):
            result[url]=row
    return result


def authoritative_page_seeds():
    """Only original-government URLs already bound to a reviewed source."""
    gis=fetch_all(api_request,"trusted_flock_gis_sources?select=source_key,government_evidence_url,"
        "jurisdiction_label&source_status=eq.verified&limit=100","source_key")
    programs=fetch_all(api_request,"flock_documented_programs?select=program_key,official_evidence_url,"
        "jurisdiction_label&record_status=eq.verified"
        "&program_status=eq.documented_at_source_date&limit=100","program_key")
    agendas=fetch_all(api_request,"verified_flock_agenda_mentions?select=tenant,matter_id,government_evidence_url,"
        "jurisdiction_label&status=eq.verified&limit=100","tenant,matter_id")
    # Original government citations are still reviewed source records.
    seeds={}
    for rows,col in ((gis,"government_evidence_url"),
                     (programs,"official_evidence_url"),
                     (agendas,"government_evidence_url")):
        for item in rows:
            url=normalized_url(item.get(col) or "")
            label=item.get("jurisdiction_label")
            if (url and isinstance(label,str) and 5<=len(label)<=150
                and len(url)<=1500):
                # This exact URL is pinned by the reviewed source database.
                # Never accept arbitrary pages suggested by the ArcGIS item.
                seeds[url]=label
    if len(seeds)>MAX_SEEDS:
        raise ValueError("Reviewed original-government page set too large")
    return seeds


def direct_candidate_links(document,page,sha,jurisdiction,known):
    if not original_camera_disclosure(document):
        return []
    output=[]
    seen=set()
    host=urllib.parse.urlsplit(page).hostname
    for href,label in document.anchors:
        if not isinstance(href,str):
            continue
        raw=urllib.parse.urljoin(page,href)
        url=normalized_url(raw)
        if not url:
            continue
        method="government_page_direct_anchor_v1"
        match=url
        if match not in known:
            # Original government page links the service directory itself;
            # map only if EXACTLY ONE known Flock-labelled feature layer is
            # associated with that service. A multi-layer service is ambiguous.
            service_matches=[candidate for candidate in known if
                candidate.rsplit("/",1)[0]==url.rstrip("/") and
                "flock" in str(known[candidate].get("layer_name","")).lower()]
            if len(service_matches)!=1:
                continue
            match=service_matches[0]
            method="government_page_direct_service_v1"
        if match in seen:
            continue
        if not LINK_LABEL.search((label or "")+" "+urllib.parse.urlsplit(url).path):
            continue
        if not (url.startswith("https://") and len(url)<=1500):
            continue
        seen.add(match)
        output.append({
          "disclosure_url":page,
          "gis_layer_url":match,
          "jurisdiction_label":jurisdiction,
          "discovery_method":method,
          "link_label":(" ".join(label.split()) or "Original government GIS camera layer")[:220],
          "government_page_sha256":sha,
          "source_host_scope":host,
          "layer_host":urllib.parse.urlsplit(url).hostname,
          "layer_metadata_status":"unverified",
        })
    return output


def stage(rows):
    for item in rows:
        receipt=api_request(
            "government_gis_disclosure_leads?on_conflict=disclosure_url,gis_layer_url",
            method="POST",payload=[item],
            prefer="resolution=ignore-duplicates,return=minimal")
        if receipt is not None:
            raise ValueError("Government link receipt rejected or unexpected")


def run(dry_run=False):
    known=candidates()
    seeds=authoritative_page_seeds()
    stats=Counter()
    stats["private_gis_candidates"]=len(known)
    stats["trusted_original_pages"]=len(seeds)
    findings={}
    if not known:
        print("No unverified GIS sources currently require government link checks")
        return stats
    for page,jurisdiction in sorted(seeds.items()):
        try:
            document,digest=fetch_government_page(page)
            stats["original_pages_checked"]+=1
            for row in direct_candidate_links(document,page,digest,jurisdiction,known):
                findings[(row["disclosure_url"],row["gis_layer_url"])]=row
        except Exception as err:
            stats["original_pages_held"]+=1
            print("Original government disclosure held:",
                  urllib.parse.urlsplit(page).hostname,
                  type(err).__name__,str(err)[:130])
    if not stats["original_pages_checked"]:
        raise ValueError("No original government pages could be independently examined")
    stats["exact_government_links"]=len(findings)
    if not dry_run:
        stage(findings.values())
        stats["private_receipts_staged"]=len(findings)
    for key in ("private_gis_candidates","trusted_original_pages",
                "original_pages_checked","original_pages_held",
                "exact_government_links","private_receipts_staged"):
        print("Candidate government link",key+":",stats[key])
    print("Camera GIS sources newly authorized by a government page link alone: 0")
    print("Camera coordinates published by hyperlink matching: 0")
    return stats


if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--dry-run",action="store_true")
    run(a.parse_args().dry_run)
