#!/usr/bin/env python3
"""Promote an exact tested commit through an HTTPS deployment hook and verify health."""

import argparse
import json
import os
import sys
import time
from urllib.request import Request, urlopen


def post_json(url, token, payload):
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "SDAC-Deploy/1"})
    with urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Deployment hook returned HTTP {response.status}")


def health_ok(url):
    with urlopen(url, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("status") == "operational"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=("staging", "production"), required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    prefix = f"SDAC_{args.environment.upper()}"
    hook = os.getenv(prefix + "_DEPLOY_HOOK", "").strip()
    rollback = os.getenv(prefix + "_ROLLBACK_HOOK", "").strip()
    health = os.getenv(prefix + "_HEALTH_URL", "").strip()
    token = os.getenv("SDAC_DEPLOY_TOKEN", "").strip()
    if not hook or not health or not token:
        raise SystemExit(f"Missing {prefix}_DEPLOY_HOOK, {prefix}_HEALTH_URL, or SDAC_DEPLOY_TOKEN")
    payload = {"environment": args.environment, "commit": args.commit, "version": args.version}
    post_json(hook, token, payload)
    for _ in range(12):
        try:
            if health_ok(health):
                print(json.dumps({**payload, "status": "healthy"}))
                return 0
        except Exception:
            pass
        time.sleep(10)
    if rollback:
        post_json(rollback, token, {**payload, "reason": "health verification failed"})
    print(json.dumps({**payload, "status": "rolled_back" if rollback else "failed"}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
