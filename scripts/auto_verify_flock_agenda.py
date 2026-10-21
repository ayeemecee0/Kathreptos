"""Automatically publish ONLY exact official-government agenda mentions of Flock Safety.

An official Legistar matter that names Flock Safety is a verifiable *mention*,
NOT proof of a government vote, executed contract, camera deployment, purchase
price, or individual officeholder position. Do not infer those claims here.

The public mention is derived from a fresh GET of the official Legistar API.
Only already verified government tenants with approved domain authority qualify.
Any missing, changed, restricted, or ambiguous record is held, not published.
"""
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

from discover_government_records import (
    USER_AGENT, get_json, registry_clients,
)

FLOCK_IN_TITLE = re.compile(r"\bflock[\s\-–—_:]+safety\b", re.I)
OFFICIAL_API = re.compile(
    r"^https://webapi\.legistar\.com/v1/([a-z0-9-]{3,40})/matters/([0-9]+)$")
MAX_REVIEW_ROWS = 1000
BATCH = 100
MAX_POST_BYTES = 50_000
MAX_TITLE_CHARS = 1000


def api_request(path, method="GET", payload=None, prefer=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {
        "apikey": key, "Authorization": "Bearer " + key,
        "Accept": "application/json", "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(MAX_POST_BYTES + 1)
    if len(raw) > MAX_POST_BYTES:
        raise ValueError("Private registry API response exceeded size limit")
    return json.loads(raw) if raw else None


def verified_registry_rows(approved_clients):
    """Require an independently verified government tenant AND live authority."""
    params = urllib.parse.urlencode({
        "select": "source_url,jurisdiction_label,evidence_url",
        "source_kind": "eq.legistar",
        "verification_status": "eq.verified",
        "limit": "500",
    })
    rows = api_request("government_source_registry?" + params)
    if not isinstance(rows, list):
        raise ValueError("Unexpected verified government registry response")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("source_url") or "")
        if not re.fullmatch(r"https://[a-z0-9-]{3,40}\.legistar\.com/", url):
            continue
        tenant = url.removeprefix("https://").split(".", 1)[0]
        label = str(row.get("jurisdiction_label") or "")
        evidence_url = str(row.get("evidence_url") or "")
        if approved_clients.get(tenant) != label or not evidence_url.startswith("https://"):
            continue
        out[tenant] = {
            "jurisdiction_label": label, "government_evidence_url": evidence_url,
        }
    return out


def staged_candidates():
    """Read staged private API matters, never public guessed Legistar page IDs."""
    rows = []
    for offset in range(0, MAX_REVIEW_ROWS, BATCH):
        query = urllib.parse.urlencode({
            "select": "tenant,matter_id,official_api_url,review_state",
            "review_state": "in.(needs_primary_review,source_verified,ready_to_publish)",
            "order": "created_at.asc",
            "limit": str(BATCH),
            "offset": str(offset),
        })
        batch = api_request("agenda_evidence_reviews?" + query)
        if not isinstance(batch, list):
            raise ValueError("Unexpected private agenda review response")
        rows.extend(batch)
        if len(batch) < BATCH:
            return rows
    if len(rows) >= MAX_REVIEW_ROWS:
        print("Private review candidate cap reached; remaining leads await next run")
    return rows


def official_mention(row, registry):
    """Validate a live API matter, then produce a narrow, exact title-only fact."""
    if not isinstance(row, dict):
        return None, "bad staged record"
    tenant = str(row.get("tenant") or "")
    mid = row.get("matter_id")
    if tenant not in registry or type(mid) is not int or mid <= 0:
        return None, "untrusted government tenant or invalid ID"
    source_url = "https://webapi.legistar.com/v1/" + tenant + "/matters/" + str(mid)
    if row.get("official_api_url") != source_url or not OFFICIAL_API.fullmatch(source_url):
        return None, "staged official API identity mismatch"
    if row.get("review_state") in ("rejected", "published"):
        return None, "previous editorial decision excludes automatic mention"

    # No search snippet, scraped claim, or user-entered data is an evidence source.
    matter = get_json(source_url)
    if not isinstance(matter, dict):
        return None, "official API did not return one matter"
    if type(matter.get("MatterId")) is not int or matter["MatterId"] != mid:
        return None, "official API MatterId mismatch"
    if matter.get("MatterRestrictViewViaWeb") is True or matter.get("MatterDeleted") is True:
        return None, "government matter is not publicly viewable"
    titles = []
    for key in ("MatterTitle", "MatterName"):
        value = matter.get(key)
        if isinstance(value, str):
            text = " ".join(value.split())
            if 12 <= len(text) <= MAX_TITLE_CHARS and FLOCK_IN_TITLE.search(text):
                titles.append(text)
    if not titles:
        return None, "official API title does not explicitly name Flock Safety"
    title = max(titles, key=len)
    # Do not infer a vote, execution, or deployment from history/description.
    file_value = matter.get("MatterFile")
    file_number = " ".join(file_value.split())[:160] if isinstance(file_value, str) else None
    raw_date = matter.get("MatterIntroDate")
    intro_date = None
    if isinstance(raw_date, str) and re.match(r"^\d{4}-\d{2}-\d{2}", raw_date):
        try:
            parsed = dt.date.fromisoformat(raw_date[:10])
            if dt.date(1990, 1, 1) <= parsed <= dt.date.today() + dt.timedelta(days=366):
                intro_date = parsed.isoformat()
        except ValueError:
            pass
    return {
        "tenant": tenant,
        "matter_id": mid,
        "jurisdiction_label": registry[tenant]["jurisdiction_label"],
        "matter_title": title,
        "file_number": file_number,
        "government_evidence_url": registry[tenant]["government_evidence_url"],
        "intro_date": intro_date,
    }, None


def submit_verified_mention(payload):
    """Insert idempotently; never change an existing publication or revocation."""
    result = api_request(
        "verified_flock_agenda_mentions?on_conflict=tenant,matter_id",
        method="POST", payload=[payload],
        prefer="resolution=ignore-duplicates,return=representation")
    if not isinstance(result, list) or len(result) > 1:
        raise ValueError("Unexpected verified mention insertion response")
    return bool(result)


def main():
    clients = registry_clients()
    registry = verified_registry_rows(clients)
    print("Independently verified government tenants eligible for auto-check:", len(registry))
    rows = staged_candidates()
    print("Private agenda matters checked for automatic exact-title verification:", len(rows))
    verifiable = 0
    published = 0
    held = 0
    errors = 0
    duplicates = 0
    for row in rows:
        try:
            claim, reason = official_mention(row, registry)
            if claim is None:
                held += 1
                continue
            verifiable += 1
            was_inserted = submit_verified_mention(claim)
            published += int(was_inserted)
            duplicates += int(not was_inserted)
        except Exception as exc:
            errors += 1
            # A fetch/verification failure never causes a public claim.
            print("Official mention held:", str(row.get("tenant") or "")[:40],
                  str(row.get("matter_id") or "")[:18],
                  type(exc).__name__, str(exc)[:120])
    print("Official Flock Safety agenda mentions confirmed against live API:", verifiable)
    print("New exact-title government agenda mentions auto-published:", published)
    print("Existing verified agenda mentions skipped:", duplicates)
    print("Agenda matters held for incomplete/ambiguous evidence:", held + errors)
    print("Contracts, approvals, votes, deployments auto-published: 0 (not proven by an agenda title)")


if __name__ == "__main__":
    main()
