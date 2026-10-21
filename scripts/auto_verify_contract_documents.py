"""Unattended, conservative original-document intake for Flock Safety agreements.

Every qualifying record establishes only that an independently verified government
Legistar matter contains a PDF attachment with contract-form text and an explicit
Flock Safety reference. A blank signature block is NOT proof of execution.
Only government-hosted, bounded, readable PDFs can pass. Scan-only PDFs and
other inaccessible records are held without publishing unsupported facts.
"""
import argparse
import hashlib
import io
import re
import urllib.parse
import urllib.request

from pypdf import PdfReader
from auto_verify_flock_agenda import (
    api_request, official_mention, staged_candidates, verified_registry_rows,
)
from auto_verify_legislative_decisions import fetch_public_mentions
from discover_government_records import get_json, registry_clients

MAX_DOC_BYTES = 8 * 1024 * 1024
MAX_PAGES = 60
MAX_ATTACHMENTS = 60
MAX_DOCUMENTS = 400
FLOCK = re.compile(r"\bflock\s+safety\b", re.I)
CONTRACT_FORM = re.compile(
    r"\b(?:master\s+(?:services?|subscription)\s+agreement|"
    r"software\s+(?:services?|subscription)\s+agreement|"
    r"this\s+(?:agreement|contract)\s+is\s+(?:made|entered|effective)|"
    r"agreement\s+(?:made|entered)\s+(?:into|by)\s+and\s+between)\b", re.I)
LEGAL_STRUCTURE = re.compile(
    r"\b(?:in\s+witness\s+whereof|term\s+and\s+termination|"
    r"limitation\s+of\s+liability|signature(?:s)?\s+of\s+the\s+parties)\b", re.I)


ATTACHMENT_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$", re.I)


def verified_document_domains(registry):
    """Bind already owner-reviewed municipal web hosts to exact verified tenants.

    News mentions and search results cannot add trusted hosts here. This API is
    backed by the existing owner-reviewed official_government_domains table.
    """
    rows = api_request(
        "official_government_domains?select=domain,jurisdiction_label,"
        "legistar_tenant,allow_www&verification_status=eq.verified&limit=500")
    if not isinstance(rows, list) or len(rows) >= 500:
        raise ValueError("Invalid or truncated verified municipal domain registry")
    domains = {tenant: set() for tenant in registry}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tenant = row.get("legistar_tenant")
        host = row.get("domain")
        label = row.get("jurisdiction_label")
        if (tenant not in registry or
                label != registry[tenant]["jurisdiction_label"] or
                not isinstance(host, str) or
                not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host)):
            continue
        domains[tenant].add(host)
        if row.get("allow_www") is True:
            domains[tenant].add("www." + host)
    return domains


def official_attachment_url(url, tenant, municipal_hosts=()):
    """Validate the exact source URL returned by a freshly verified Legistar API.

    Platform PDF hosts are restricted to tenant-scoped immutable-UUID paths.
    Additional municipal hosts require an *existing owner-reviewed* domain
    authority; merely ending in .gov never grants access.
    """
    if (not isinstance(url, str) or not isinstance(tenant, str)
            or not re.fullmatch(r"[a-z0-9-]{3,40}", tenant)
            or len(url) > 2048 or any(c.isspace() for c in url) or "\\" in url):
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        if (parsed.scheme != "https" or parsed.netloc != hostname
                or parsed.username or parsed.password or parsed.port is not None
                or parsed.fragment):
            return None
        if hostname == tenant + ".legistar.com" and parsed.path.lower() == "/view.ashx":
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if (set(query) != {"M", "ID"} or query["M"] != ["F"] or
                    len(query["ID"]) != 1 or
                    not re.fullmatch(r"[0-9]{1,18}", query["ID"][0])):
                return None
            return url
        if parsed.query:
            return None
        allowed_vendor = (
            tenant + ".legistar.com", tenant + ".legistar1.com",
            "legistar.granicus.com", "legistar1.granicus.com")
        if hostname in allowed_vendor:
            bits = parsed.path.split("/")
            if (len(bits) == 4 and bits[0] == "" and
                    bits[1].casefold() == tenant.casefold() and
                    bits[2].lower() == "attachments" and
                    ATTACHMENT_UUID.fullmatch(bits[3])):
                return url
        if hostname in municipal_hosts and parsed.path.lower().endswith(".pdf"):
            path = urllib.parse.unquote(parsed.path)
            if (path.startswith("/") and not any(
                    part in (".", "..") for part in path.split("/"))
                    and not any(ord(c) < 32 for c in path)):
                return url
        return None
    except (ValueError, TypeError, AttributeError):
        return None


class SameGovernmentHostRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, tenant, municipal_hosts=()):
        self.tenant = tenant
        self.municipal_hosts = municipal_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not official_attachment_url(newurl, self.tenant, self.municipal_hosts):
            raise ValueError("Government attachment redirected outside approved host/path")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_document(url, tenant, municipal_hosts=()):
    if not official_attachment_url(url, tenant, municipal_hosts):
        raise ValueError("Not an allowed government attachment")
    opener = urllib.request.build_opener(SameGovernmentHostRedirect(tenant, municipal_hosts))
    request = urllib.request.Request(
        url, headers={"Accept": "application/pdf", "User-Agent": "Katoptron/1.0 public records research"})
    with opener.open(request, timeout=15) as response:
        actual = response.geturl()
        if not official_attachment_url(actual, tenant, municipal_hosts):
            raise ValueError("Government attachment final URL was not approved")
        data = response.read(MAX_DOC_BYTES + 1)
    if len(data) > MAX_DOC_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Document missing PDF magic or exceeds bounded size")
    return data

def contract_pdf_evidence(pdf_bytes, jurisdiction_label):
    """Identify contract-like documents without ever inferring a signature."""
    if not isinstance(pdf_bytes, bytes) or len(pdf_bytes) < 200:
        return None, "invalid PDF data"
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=True)
        if reader.is_encrypted:
            return None, "encrypted PDF held"
        pages = len(reader.pages)
        if not 1 <= pages <= MAX_PAGES:
            return None, "PDF page limit exceeded"
        pieces = []
        for page in reader.pages:
            value = page.extract_text()
            if isinstance(value, str):
                pieces.append(value[:20_000])
        text = " ".join(pieces)[:250_000]
    except Exception as exc:
        return None, "PDF parsing failed: " + type(exc).__name__
    if not FLOCK.search(text):
        return None, "PDF itself does not explicitly name Flock Safety"
    if not CONTRACT_FORM.search(text) or not LEGAL_STRUCTURE.search(text):
        return None, "no clear agreement-form body and legal clauses"
    # A record may reference a town in the matter title while the attachment
    # is a generic unexecuted vendor template. Require the local public body
    # in the actual PDF, too.
    local = jurisdiction_label.split(",", 1)[0].strip()
    if len(local) < 4 or not re.search(re.escape(local), text, re.I):
        return None, "government contracting party not explicitly identified in PDF"
    return {"pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "pdf_bytes": len(pdf_bytes), "pdf_pages": pages}, None


def attachment_metadata(attachment, tenant, matter_id, municipal_hosts=()):
    if not isinstance(attachment, dict):
        return None
    aid = attachment.get("MatterAttachmentId")
    if type(aid) is not int or aid <= 0:
        return None
    specified_parent = attachment.get("MatterAttachmentMatterId")
    if specified_parent is not None and specified_parent != matter_id:
        return None
    if attachment.get("MatterAttachmentShowOnInternetPage") is False:
        return None
    url = official_attachment_url(attachment.get("MatterAttachmentHyperlink"), tenant, municipal_hosts)
    if not url:
        return None
    name = attachment.get("MatterAttachmentName")
    if not isinstance(name, str) or len(name.strip()) < 4:
        name = "Official government document " + str(aid)
    name = " ".join(name.split())
    if len(name) > 240:
        return None
    return aid, name, url


def public_document(row, parent, attachment, pdf_info):
    aid, name, url = attachment
    return {
        "tenant": row["tenant"], "matter_id": row["matter_id"],
        "attachment_id": aid, "jurisdiction_label": parent["jurisdiction_label"],
        "matter_title": parent["matter_title"], "attachment_name": name,
        "document_url": url, **pdf_info,
    }


def prior_document(tenant, matter_id, attachment_id):
    query = urllib.parse.urlencode({
        "select": "pdf_sha256,status", "tenant": "eq." + tenant,
        "matter_id": "eq." + str(matter_id),
        "attachment_id": "eq." + str(attachment_id), "limit": "1",
    })
    rows = api_request("official_flock_contract_documents?" + query)
    if not isinstance(rows, list) or len(rows) > 1:
        raise ValueError("Unrecognized existing contract-document receipt")
    return rows[0] if rows else None


def publish_document(payload):
    result = api_request(
        "official_flock_contract_documents?on_conflict=tenant,matter_id,attachment_id",
        method="POST", payload=[payload],
        prefer="resolution=ignore-duplicates,return=representation")
    if not isinstance(result, list) or len(result) > 1:
        raise ValueError("Invalid contract-document publication receipt")
    return bool(result)


def revoke_changed_document(payload):
    params = urllib.parse.urlencode({
        "tenant": "eq." + payload["tenant"],
        "matter_id": "eq." + str(payload["matter_id"]),
        "attachment_id": "eq." + str(payload["attachment_id"]),
        "status": "eq.verified",
    })
    result = api_request("official_flock_contract_documents?" + params,
                         method="PATCH", payload={"status": "revoked"},
                         prefer="return=representation")
    if not isinstance(result, list) or len(result) > 1:
        raise ValueError("Invalid contract-document revocation receipt")
    return bool(result)


def run(dry_run=False):
    registry = verified_registry_rows(registry_clients())
    parents = fetch_public_mentions()
    staged = staged_candidates()
    municipal_domains = verified_document_domains(registry)
    seen = set()
    totals = {"matters": 0, "attachments": 0, "rejected_links": 0, "qualified": 0,
              "published": 0, "existing": 0, "revoked": 0,
              "held": 0, "errors": 0}
    for row in staged:
        if not isinstance(row, dict):
            continue
        tenant, mid = row.get("tenant"), row.get("matter_id")
        key = (tenant, mid)
        if key in seen or key not in parents or tenant not in registry:
            continue
        seen.add(key)
        try:
            parent = parents[key]
            fresh, reason = official_mention(row, registry)
            if (reason or not fresh or
                    fresh["matter_title"] != parent["matter_title"] or
                    fresh["file_number"] != parent["file_number"] or
                    parent.get("jurisdiction_label") != registry[tenant]["jurisdiction_label"]):
                totals["held"] += 1
                continue
            totals["matters"] += 1
            url = "https://webapi.legistar.com/v1/" + tenant + "/matters/" + str(mid) + "/attachments"
            items = get_json(url)
            if not isinstance(items, list) or len(items) > MAX_ATTACHMENTS:
                totals["held"] += 1
                continue
            print("Verified government matter attachment count:", tenant, mid, len(items))
            document_ids = set()
            for item in items:
                metadata = attachment_metadata(item, tenant, mid, municipal_domains.get(tenant, ()))
                if metadata is None:
                    totals["rejected_links"] += 1
                    continue
                if metadata[0] in document_ids:
                    continue
                document_ids.add(metadata[0])
                if totals["attachments"] >= MAX_DOCUMENTS:
                    print("Document safety cap reached; remainder deferred")
                    break
                totals["attachments"] += 1
                aid, name, href = metadata
                try:
                    pdf = fetch_document(href, tenant, municipal_domains.get(tenant, ()))
                    info, issue = contract_pdf_evidence(pdf, parent["jurisdiction_label"])
                    if issue:
                        totals["held"] += 1
                        continue
                    totals["qualified"] += 1
                    claim = public_document(row, parent, metadata, info)
                    if dry_run:
                        print("DRY-RUN government agreement document:", tenant, mid, aid, info["pdf_sha256"][:14])
                        continue
                    previous = prior_document(tenant, mid, aid)
                    if previous:
                        if previous.get("status") == "verified" and previous.get("pdf_sha256") != info["pdf_sha256"]:
                            if revoke_changed_document(claim):
                                totals["revoked"] += 1
                            print("Changed government PDF fingerprint; withdrawn pending new independent verification:", tenant, mid, aid)
                        else:
                            totals["existing"] += 1
                    elif publish_document(claim):
                        totals["published"] += 1
                    else:
                        totals["existing"] += 1
                except Exception as exc:
                    totals["errors"] += 1
                    print("Contract attachment held:", tenant, mid, aid,
                          type(exc).__name__, str(exc)[:120])
        except Exception as exc:
            totals["errors"] += 1
            print("Contract matter held:", str(tenant)[:35], str(mid)[:20],
                  type(exc).__name__, str(exc)[:120])
    for field, n in totals.items():
        print("Contract document", field + ":", n)
    print("Signed contracts, executions, payments and camera deployments inferred: 0")
    return totals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    run(dry_run=parser.parse_args().dry_run)
