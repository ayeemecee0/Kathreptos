"""Automatically verify PUBLIC Flock Safety legislative ACTION EVENTS.

Only exact, independently verified Flock government matters qualify. A history
row is published only if it contains (1) a known, final-action verb, (2) a
matching explicit pass/fail flag, (3) a true legislative governing body,
(4) a valid dated official action and (5) a stable integer Legistar history ID.

Individual votes, a municipality's ultimate policy status, executed contracts,
money spent and installed cameras are NEVER inferred by this module.

Every public entry names a SPECIFIC action on a SPECIFIC matter/date. Some
matters have both failed and adopted actions at different times. Both are
recorded as separate events with their original official government URLs.
"""
import argparse
import collections
import datetime as dt
import re

from auto_verify_flock_agenda import (
    api_request, official_mention, staged_candidates, verified_registry_rows,
)
from discover_government_records import get_json, registry_clients

# Strict, explicit legislative action/flag pairs only. Excludes "Recommended
# for Adoption", "Passed on First Reading", "Referred", "Filed", "Received",
# "Introduced", "Discussed" and any ambiguous/committee-only outcomes.
ACTION_OUTCOMES = {
    "adopted": "adopted",
    "adopted as amended": "adopted_as_amended",
    "approved": "approved",
    "approved as amended": "approved_as_amended",
    "failed": "failed",
    "rejected": "rejected",
}
SUCCESS = frozenset(("adopted", "adopted_as_amended", "approved", "approved_as_amended"))
ALLOWED_PASS_FLAGS = frozenset(("pass", "passed"))
ALLOWED_FAIL_FLAGS = frozenset(("fail", "failed"))

# Non-legislative committees or staff cannot approve citywide agreements.
# Body identity MUST match exactly, no substring/heuristic matching.
GOVERNING_BODIES = frozenset((
    "city council", "common council", "county council", "county board",
    "board of supervisors", "board of county commissioners",
    "city commission", "county commission", "town council", "village board",
    "municipal council", "city council of the city of oakland",
))
MAX_HISTORIES_PER_MATTER = 200
MAX_MENTIONS = 500
MAX_TITLE_LENGTH = 1000
MAX_EVENT_TEXT_LENGTH = 100
MAX_BODY_LENGTH = 120


def normalize(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split()).casefold()


def exact_action_event(history, mention, today=None):
    """Return a narrow, supported public event or a reason to retain privately."""
    if not isinstance(history, dict) or not isinstance(mention, dict):
        return None, "invalid government history record"
    event_id = history.get("MatterHistoryId")
    if type(event_id) is not int or event_id <= 0:
        return None, "missing exact official history ID"

    action = normalize(history.get("MatterHistoryActionName"))
    outcome = ACTION_OUTCOMES.get(action)
    if outcome is None:
        return None, "not an unequivocal legislative action"
    pass_name = normalize(history.get("MatterHistoryPassedFlagName"))
    wanted = ALLOWED_PASS_FLAGS if outcome in SUCCESS else ALLOWED_FAIL_FLAGS
    if pass_name not in wanted:
        return None, "legislative action not corroborated by matching pass/fail result"

    body = normalize(history.get("MatterHistoryActionBodyName"))
    if body not in GOVERNING_BODIES:
        return None, "action not by a known legislative governing body"
    when = history.get("MatterHistoryActionDate")
    if not isinstance(when, str) or not re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", when):
        return None, "no valid official action date"
    try:
        day = dt.date.fromisoformat(when[:10])
    except ValueError:
        return None, "invalid official action date"
    if day < dt.date(1990, 1, 1) or day > (today or dt.date.today()) + dt.timedelta(days=1):
        return None, "historical action date outside credible date bounds"

    title = mention.get("matter_title")
    if not isinstance(title, str) or not 12 <= len(title) <= MAX_TITLE_LENGTH:
        return None, "matter title not valid"
    action_name = " ".join(history["MatterHistoryActionName"].split())
    body_name = " ".join(history["MatterHistoryActionBodyName"].split())
    pass_flag = " ".join(history["MatterHistoryPassedFlagName"].split())
    if not (len(action_name) <= MAX_EVENT_TEXT_LENGTH and len(body_name) <= MAX_BODY_LENGTH):
        return None, "government history field too long"
    return {
        "tenant": mention["tenant"],
        "matter_id": mention["matter_id"],
        "history_id": event_id,
        "jurisdiction_label": mention["jurisdiction_label"],
        "matter_title": title,
        "file_number": mention.get("file_number"),
        "action_name": action_name,
        "action_body": body_name,
        "passed_flag_name": pass_flag,
        "decision_outcome": outcome,
        "action_date": day.isoformat(),
    }, None


def get_history_events(row, registry, parent):
    """Fresh re-check of parent government matter AND exact action history IDs."""
    if not isinstance(row, dict) or not isinstance(parent, dict):
        return [], "missing verified official matter"
    tenant = row.get("tenant")
    mid = row.get("matter_id")
    if (not isinstance(tenant, str) or tenant not in registry
            or type(mid) is not int or mid <= 0
            or row.get("review_state") not in (
                "needs_primary_review", "source_verified", "ready_to_publish")):
        return [], "unauthorized, rejected, or already manually published matter"
    if (parent.get("tenant") != tenant or parent.get("matter_id") != mid
            or parent.get("status") != "verified"
            or parent.get("jurisdiction_label") != registry[tenant]["jurisdiction_label"]):
        return [], "source-verified government matter mismatch"

    current, reason = official_mention(row, registry)  # exact fresh GET, Flock title
    if reason or current is None:
        return [], reason or "parent government matter no longer qualifies"
    if (current["matter_title"] != parent.get("matter_title")
            or current["file_number"] != parent.get("file_number")):
        return [], "official matter title or file changed since original verification"

    url = f"https://webapi.legistar.com/v1/{tenant}/matters/{mid}/histories"
    histories = get_json(url)
    if not isinstance(histories, list) or len(histories) > MAX_HISTORIES_PER_MATTER:
        return [], "government API history missing, malformed or above bounded limit"
    decisions = {}
    conflicting = set()
    for history in histories:
        action, reason = exact_action_event(history, current)
        if action is None:
            continue
        ident = action["history_id"]
        if ident in decisions and decisions[ident] != action:
            conflicting.add(ident)
        else:
            decisions[ident] = action
    for ident in conflicting:
        del decisions[ident]
    return list(decisions.values()), (
        "conflicting official history IDs held" if conflicting else None)


def fetch_public_mentions():
    """Read only public/previously verified Flock matters as candidate parents."""
    result = []
    for offset in range(0, MAX_MENTIONS, 100):
        from urllib.parse import urlencode
        path = "verified_flock_agenda_mentions?" + urlencode({
            "select": "tenant,matter_id,jurisdiction_label,matter_title,file_number,status",
            "status": "eq.verified",
            "order": "tenant.asc,matter_id.asc",
            "limit": "100", "offset": str(offset),
        })
        rows = api_request(path)
        if not isinstance(rows, list):
            raise ValueError("Unexpected verified Flock mention response")
        result.extend(rows)
        if len(rows) < 100:
            break
    if len(result) >= MAX_MENTIONS:
        print("Verified Flock mention safety cap reached; older parents deferred")
    return {(r["tenant"], r["matter_id"]): r for r in result
            if isinstance(r, dict) and isinstance(r.get("tenant"), str)
            and type(r.get("matter_id")) is int}


def insert_verified_decision(decision):
    response = api_request(
        "verified_flock_legislative_decisions?on_conflict=tenant,matter_id,history_id",
        method="POST", payload=[decision],
        prefer="resolution=ignore-duplicates,return=representation")
    if not isinstance(response, list) or len(response) > 1:
        raise ValueError("Unexpected publication receipt from Supabase")
    return bool(response)


def run(dry_run=False, show_actions=False):
    registry = verified_registry_rows(registry_clients())
    parents = fetch_public_mentions()
    staged = staged_candidates()
    print("Verified government authority bindings:", len(registry))
    print("Currently verified explicit-Flock official matters:", len(parents))
    print("Private matters staged for action-history verification:", len(staged))
    eligible = 0
    published = 0
    existing = 0
    held = 0
    errors = 0
    seen = set()
    for row in staged:
        if not isinstance(row, dict):
            continue
        key = (row.get("tenant"), row.get("matter_id"))
        if key in seen or key not in parents:
            continue
        seen.add(key)
        try:
            events, issue = get_history_events(row, registry, parents[key])
            if issue:
                print("Matter decision verification warning:",
                      str(key[0])[:40], str(key[1])[:18], issue)
            if not events:
                held += 1
            for event in events:
                eligible += 1
                if dry_run:
                    print("DRY-RUN decision event:", event["tenant"], event["matter_id"],
                          event["history_id"], event["action_name"],
                          event["passed_flag_name"], event["action_body"],
                          event["action_date"])
                elif insert_verified_decision(event):
                    published += 1
                else:
                    existing += 1
            if show_actions:
                url = f"https://webapi.legistar.com/v1/{key[0]}/matters/{key[1]}/histories"
                histories = get_json(url)
                if isinstance(histories, list):
                    summaries = collections.Counter((
                        normalize(h.get("MatterHistoryActionName")),
                        normalize(h.get("MatterHistoryPassedFlagName")),
                        normalize(h.get("MatterHistoryActionBodyName")),
                    ) for h in histories[:MAX_HISTORIES_PER_MATTER] if isinstance(h, dict))
                    for (action, flag, body), count in summaries.most_common(20):
                        print("HISTORY FIELDS:", str(key[0])[:40],
                              str(key[1])[:18], action[:75], flag[:30],
                              body[:100], "x", count)
        except Exception as exc:
            errors += 1
            print("Decision held due to official-source error:", str(key[0])[:40],
                  str(key[1])[:18], type(exc).__name__, str(exc)[:160])
    print("Source-corroborated legislative action events:", eligible)
    print("New government legislative events auto-published:", published)
    print("Previously verified legislative events skipped:", existing)
    print("Explicit Flock matters without provable legislative outcomes:", held)
    print("Government histories held due to errors:", errors)
    print("Signed contracts, individual votes and deployments inferred: 0")
    return {"eligible": eligible, "published": published, "existing": existing,
            "held": held, "errors": errors}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dry-run", action="store_true",
                     help="Fetch/validate official records without publishing")
    cli.add_argument("--show-actions", action="store_true",
                     help="Log non-sensitive official action names, flags and bodies")
    args = cli.parse_args()
    run(dry_run=args.dry_run, show_actions=args.show_actions)
