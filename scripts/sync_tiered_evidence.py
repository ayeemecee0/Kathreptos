"""Reconcile existing private candidate queues with independently trusted evidence.

No approval input is accepted here. PostgreSQL derives camera-source evidence
from its already verified GIS camera inventory and guarded community matches.
The only automatic publication route requires attestations already reviewed
and authorized independently of discovery jobs.
"""
import argparse
from collections import Counter

from auto_verify_flock_agenda import api_request

MAX_ROUNDS=18
MAX_BATCH=600


def invoke(function_name,limit):
    if not (1<=limit<=MAX_BATCH):
        raise ValueError("Illegal bounded evidence batch")
    result=api_request("rpc/"+function_name,method="POST",
        payload={"p_limit":limit})
    if not isinstance(result,dict):
        raise ValueError("Unexpected tiered-evidence RPC response")
    if any(type(v) is not int or v<0 for v in result.values()):
        raise ValueError("Invalid tiered-evidence RPC counts")
    return result


def run(rounds=15,limit=600):
    if not 1<=rounds<=MAX_ROUNDS:
        raise ValueError("Invalid bounded staging rounds")
    totals=Counter()
    for i in range(rounds):
        result=invoke("stage_tiered_evidence_from_verified_matches",limit)
        totals.update(result)
        if not result.get("staged_cases",0):
            break
    final=invoke("reconcile_tiered_evidence_cases",limit)
    totals.update(final)
    for k in sorted(totals):
        print("Trusted-evidence bridge",k+":",totals[k])
    print("Cases automatically confirmed by raw discovery: 0")
    print("Published case count must be read from live RLS, not discovery submissions")
    return totals


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit",type=int,default=600)
    ap.add_argument("--rounds",type=int,default=15)
    args=ap.parse_args()
    run(rounds=args.rounds,limit=args.limit)
