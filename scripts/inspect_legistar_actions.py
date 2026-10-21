"""Inspect PUBLIC Legistar event fields to calibrate conservative decision verification.

Read-only, allowlisted diagnostic. No Supabase credentials or private queue data.
"""
import json
from discover_government_records import get_json

ITEMS = (
    ("oakland", 36866),
    ("oakland", 36760),
    ("costamesa", 2660),
    ("commerce", 12379),
    ("commerce", 12775),
    ("mountainview", 8543),
    ("costamesa", 3763),
)

def main():
    for tenant, matter_id in ITEMS:
        base = f"https://webapi.legistar.com/v1/{tenant}/matters/{matter_id}"
        try:
            matter = get_json(base)
            histories = get_json(base + "/histories")
            print("MATTER", tenant, matter_id,
                  json.dumps({
                    "MatterId": matter.get("MatterId"),
                    "MatterFile": matter.get("MatterFile"),
                    "MatterStatusName": matter.get("MatterStatusName"),
                    "MatterFinalActionDate": matter.get("MatterFinalActionDate"),
                    "MatterPassedDate": matter.get("MatterPassedDate"),
                    "histories": len(histories),
                }, ensure_ascii=False))
            for h in histories[:35]:
                print("HISTORY", json.dumps({
                    k: h.get(k) for k in (
                        "MatterHistoryId", "MatterHistoryActionDate",
                        "MatterHistoryActionBodyName", "MatterHistoryActionName",
                        "MatterHistoryPassedFlag", "MatterHistoryPassedFlagName",
                        "MatterHistoryTally", "MatterHistoryActionText"
                    )
                }, ensure_ascii=False)[:900])
        except Exception as exc:
            print("PROBE UNAVAILABLE", tenant, matter_id, type(exc).__name__, str(exc)[:150])

if __name__ == "__main__":
    main()
