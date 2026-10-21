"""Automate only *explicitly recorded* government legislative actions.

A verified Flock Safety matter's official Legistar History contains
MatterHistoryActionName (motion), MatterHistoryPassedFlag and
MatterHistoryPassedFlagName (recorded result), MatterHistoryActionBodyName
(the acting body), and MatterHistoryActionDate (the event date).

Publish separate factual events; never equate a committee failure with a
failed city-council resolution, or an adoption with an executed agreement.
Unclear/missing/conflicting fields are held, not guessed.
"""
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from auto_verify_flock_agenda import (
    FLOCK_IN_TITLE, api_request, staged_candidates, verified_registry_rows,
)
from discover_government_records import (
    API_RESPONSE_BYTES, USER_AGENT, registry_clients,
)

MAX_MENTIONS = 1000
PAGE_SIZE = 100
MAX_HISTORIES = 80
HISTORY_ACTION_RE = re.compile(r"^(?:approved|adopted|passed|rejected|failed|denied|motion(?:\s|$))", re.I)

# Explicit city/county governing-body names. Others must be reviewed before
# adding an alias. A committee always remains a committee, even if it uses
# the words "City Council" as part of its name.
GOVERNING_BODIES = frozenset({
    "city council", "town council", "common council",
    "county council", "county commission", "city commission",
    "board of supervisors", "board of county commissioners",
    "board of commissioners", "board of aldermen",
    "board of trustees", "village board", "county board",
})
GOVERNING_BODY_ALIASES = frozenset({
    # Explicit body name verified in Oakland's live 2025 Legistar history.
    ("oakland", "special concurrent meeting of the oakland redevelopment successor agency/city council"),
})


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected redirect from official government API")


def official_json(tenant, matter_id, suffix=""):
    """Read only an exact public government API endpoint, never arbitrary URLs."""
    if (not isinstance(tenant, str)
        or not re.fullmatch(r"[a-z0-9-]{3,40}", tenant)
        or type(matter_id) is not int or matter_id < 1
        or suffix not in ("", "/histories")):
        raise ValueError("Invalid official government API reference")
    url = f"https://webapi.legistar.com/v1/{tenant}/matters/{matter_id}{suffix}"
    opener = urllib.request.build_opener(RefuseRedirect())
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
    })
    with opener.open(request, timeout=12) as response:
        if response.geturl() != url:
            raise ValueError("Official API response changed identity")
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" not in content_type:
            raise ValueError("Official API did not return JSON")
        raw = response.read(API_RESPONSE_BYTES + 1)
    if len(raw) > API_RESPONSE_BYTES:
        raise ValueError("Official government API response exceeds size limit")
    return json.loads(raw)


def government_body(tenant, name):
    if not isinstance(name, str):
        return None
    clean = " ".join(name.lstrip("*").split())
    if not 4 <= len(clean) <= 250:
        return None
    normalized = clean.casefold()
    if (tenant, normalized) in GOVERNING_BODY_ALIASES:
        return "governing_body", clean
    if "committee" in normalized:
        return "committee", clean
    if normalized in GOVERNING_BODIES:
        return "governing_body", clean
    return None


def recorded_outcome(scope, action, flag, flag_name):
    """Never infer an adoption from the text of an attempted/failed motion."""
    if not isinstance(action, str):
        return None
    normalized = " ".join(action.split()).casefold()
    if not 4 <= len(normalized) <= 300:
        return None

    # A recorded Fail takes priority even when the motion says "Approved".
    if type(flag) is int and flag == 0 and flag_name == "Fail":
        return "motion_failed" if HISTORY_ACTION_RE.match(normalized) else None

    if scope != "governing_body":
        return None
    if type(flag) is int and flag == 1 and flag_name == "Pass":
        return {
            "adopted": "adopted",
            "adopted as amended": "adopted_as_amended",
            "approved": "approved",
        }.get(normalized)
    # Explicit non-voting information events are not adoptions.
    if flag is None and flag_name is None:
        return {
            "discussed and closed": "discussed_and_closed",
            "received and filed": "received_and_filed",
        }.get(normalized)
    return None


def action_date(value):
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d\d-\d\dT", value):
        return None
    try:
        date = dt.date.fromisoformat(value[:10])
    except ValueError:
        return None
    # Future-dated actions and obviously malformed historic events are held.
    if not dt.date(1990, 1, 1) <= date <= dt.date.today():
        return None
    return date.isoformat()


def same_verified_matter(matter, mention):
    """Published Flock-specific agenda title is checked again, not taken on trust."""
    if not isinstance(matter, dict):
        return False
    mid = mention.get("matter_id")
    if type(mid) is not int or type(matter.get("MatterId")) is not int:
        return False
    if mid != matter["MatterId"]:
        return False
    if matter.get("MatterRestrictViewViaWeb") is True or matter.get("MatterDeleted") is True:
        return False
    title = mention.get("matter_title")
    if not isinstance(title, str) or not FLOCK_IN_TITLE.search(title):
        return False
    titles = [
        " ".join(v.split())
        for key in ("MatterTitle", "MatterName")
        if isinstance(v := matter.get(key), str)
    ]
    if title not in titles:
        return False
    file_number = mention.get("file_number")
    actual_file = matter.get("MatterFile")
    if isinstance(actual_file, str):
        actual_file = " ".join(actual_file.split())[:160]
    else:
        actual_file = None
    return file_number == actual_file


def decision_events(mention, matter, histories, registry):
    """Build event-level facts from explicit *matching* live official history."""
    if not isinstance(mention, dict) or not isinstance(histories, list):
        return [], "Invalid official government history"
    tenant = mention.get("tenant")
    mid = mention.get("matter_id")
    if (not isinstance(tenant, str)
        or tenant not in registry
        or mention.get("jurisdiction_label") != registry[tenant]["jurisdiction_label"]
        or not same_verified_matter(matter, mention)):
        return [], "Government identity, vendor title, or MatterId changed"
    if len(histories) > MAX_HISTORIES:
        return [], "Official history exceeds bounded processing limit"

    decisions = []
    seen = set()
    for history in histories:
        if not isinstance(history, dict):
            continue
        hid = history.get("MatterHistoryId")
        if type(hid) is not int or hid < 1 or hid in seen:
            continue
        seen.add(hid)
        body = government_body(tenant, history.get("MatterHistoryActionBodyName"))
        if body is None:
            continue
        scope, body_name = body
        name = history.get("MatterHistoryActionName")
        flag = history.get("MatterHistoryPassedFlag")
        flag_name = history.get("MatterHistoryPassedFlagName")
        outcome = recorded_outcome(scope, name, flag, flag_name)
        date = action_date(history.get("MatterHistoryActionDate"))
        if outcome is None or date is None:
            continue
        decisions.append({
            "tenant": tenant,
            "matter_id": mid,
            "history_id": hid,
            "jurisdiction_label": registry[tenant]["jurisdiction_label"],
            "matter_title": mention["matter_title"],
            "file_number": mention.get("file_number"),
            "action_date": date,
            "acting_body": body_name,
            "body_scope": scope,
            "recorded_action_name": " ".join(name.split()),
            "outcome": outcome,
            "passed_flag": flag,
            "passed_flag_name": flag_name,
        })
    return decisions, None


def verified_mentions():
    """All source-verified agenda mentions, paginated and bounded."""
    rows = []
    for offset in range(0, MAX_MENTIONS, PAGE_SIZE):
        query = urllib.parse.urlencode({
            "select": "tenant,matter_id,jurisdiction_label,matter_title,file_number,status",
            "status": "eq.verified",
            "order": "verified_at.desc",
            "offset": str(offset), "limit": str(PAGE_SIZE),
        })
        batch = api_request("verified_flock_agenda_mentions?" + query)
        if not isinstance(batch, list):
            raise ValueError("Unexpected official mention response")
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return rows


def submit_decision(event):
    result = api_request(
        "verified_flock_legislative_actions?on_conflict=tenant,matter_id,history_id",
        method="POST", payload=[event],
        prefer="resolution=ignore-duplicates,return=representation")
    if not isinstance(result, list) or len(result) > 1:
        raise ValueError("Unexpected verified action insertion response")
    return bool(result)


def main():
    registry = verified_registry_rows(registry_clients())
    eligible = {
        (r["tenant"], r["matter_id"])
        for r in staged_candidates()
        if isinstance(r, dict)
        and r.get("review_state") in ("needs_primary_review", "source_verified", "ready_to_publish")
    }
    mentions = verified_mentions()
    checked = published = duplicates = held = errors = 0
    for mention in mentions:
        tenant = mention.get("tenant")
        mid = mention.get("matter_id")
        if tenant not in registry or (tenant, mid) not in eligible:
            held += 1
            continue
        try:
            matter = official_json(tenant, mid)
            histories = official_json(tenant, mid, "/histories")
            events, reason = decision_events(mention, matter, histories, registry)
            if reason:
                held += 1
                continue
            checked += 1
            if not events:
                held += 1
            for event in events:
                inserted = submit_decision(event)
                published += int(inserted)
                duplicates += int(not inserted)
        except Exception as exc:
            errors += 1
            print("Decision evidence held:", str(tenant)[:40], str(mid)[:20],
                  type(exc).__name__, str(exc)[:140])
    print("Live official Flock matters with history checked:", checked)
    print("New body-scoped legislative actions independently verified:", published)
    print("Existing verified legislative actions skipped:", duplicates)
    print("Matters held for ambiguity or insufficient recorded action:", held)
    print("Matters held after API/verification failures:", errors)
    print("Signed contracts, deployments, expenditures, individual votes inferred: 0")


if __name__ == "__main__":
    main()
