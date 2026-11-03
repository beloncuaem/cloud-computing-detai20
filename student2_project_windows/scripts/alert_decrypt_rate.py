#!/usr/bin/env python3
"""Detect an abnormal decryption rate in a Vault audit log.

The script reads Vault audit JSON lines (file audit device), keeps the
transit/decrypt requests per identity, and finds the maximum count inside a
sliding window. It prints ALERT and exits 2 when the threshold is reached.

Example:
    docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim \
        python student2_project_windows/scripts/alert_decrypt_rate.py \
        --log bench/results/audit_attack.log --threshold 200 --window 60
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from datetime import datetime


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, help="path to the Vault audit JSON log")
    parser.add_argument("--threshold", type=int, default=200, help="alerts at or above this count")
    parser.add_argument("--window", type=int, default=60, help="sliding window in seconds")
    args = parser.parse_args()

    events: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    malformed = 0

    with open(args.log, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if entry.get("type") != "request":
                continue
            request = entry.get("request") or {}
            path = request.get("path") or ""
            if not path.startswith("transit/decrypt/"):
                continue
            timestamp = parse_time(entry.get("time"))
            if timestamp is None:
                malformed += 1
                continue
            auth = entry.get("auth") or {}
            identity = (
                auth.get("display_name")
                or auth.get("entity_id")
                or auth.get("accessor")
                or "unknown"
            )
            events[identity].append((timestamp, path))

    if not events:
        print(f"No transit/decrypt request found in {args.log} (malformed lines: {malformed})")
        return 0

    alerts = 0
    for identity, items in sorted(events.items()):
        items.sort(key=lambda item: item[0])
        first_seen = items[0][0]
        threshold_time: datetime | None = None
        window: deque[tuple[datetime, str]] = deque()

        for timestamp, path in items:
            window.append((timestamp, path))
            while window and (timestamp - window[0][0]).total_seconds() > args.window:
                window.popleft()
            if len(window) >= args.threshold and threshold_time is None:
                threshold_time = timestamp

        if threshold_time is None:
            print(
                f"OK    identity={identity} requests={len(items)} "
                f"threshold={args.threshold}/{args.window}s"
            )
            continue

        alerts += 1
        latency = (threshold_time - first_seen).total_seconds()
        print(
            f"ALERT identity={identity} requests={len(items)} "
            f"threshold={args.threshold}/{args.window}s "
            f"first_seen={first_seen.isoformat()} "
            f"threshold_reached={threshold_time.isoformat()} "
            f"latency={latency:.1f}s"
        )

    if alerts:
        print(f"\n{alerts} identity/identities exceeded the threshold.")
        return 2

    print("\nNo identity exceeded the threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
