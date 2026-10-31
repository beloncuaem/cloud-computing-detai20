#!/usr/bin/env python3
"""Summarize k6 CSV exports into p50/p95/p99 for the report.

Usage:
    python bench/analyze.py "bench/results/*.csv"
    docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim \
        python bench/analyze.py "bench/results/*.csv"

The script uses only the Python standard library. It groups files by the
configuration and VU count encoded in the file name, for example:
    D-lab_50_run1.csv  -> config=D-lab, vus=50, run=run1
    A_10_run3.csv      -> config=A, vus=10, run=run3
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import statistics
from collections import defaultdict
from pathlib import Path

NAME_RE = re.compile(r"^(?P<config>[A-Za-z][A-Za-z0-9'-]*)_(?P<vus>\d+)_run(?P<run>\d+)\.csv$")


def quantile(values: list[float], q: float) -> float:
    """Linear-interpolated quantile (same idea as numpy's default)."""
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def read_durations(path: Path) -> list[float]:
    values: list[float] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("metric_name") != "http_req_duration":
                continue
            raw = row.get("metric_value")
            if not raw:
                continue
            try:
                values.append(float(raw))
            except ValueError:
                continue
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "patterns",
        nargs="*",
        default=["bench/results/*.csv"],
        help="glob pattern(s) for k6 CSV exports",
    )
    args = parser.parse_args()

    files: list[Path] = []
    for pattern in args.patterns:
        files.extend(Path(p) for p in sorted(glob.glob(pattern)))
    files = list(dict.fromkeys(files))

    if not files:
        raise SystemExit("No CSV files matched. Run k6 with --out csv=bench/results/....csv first.")

    per_file: list[tuple[Path, int, float, float, float, float]] = []
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)

    print("| File | Samples | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |")
    print("|---|---:|---:|---:|---:|---:|")
    for path in files:
        values = read_durations(path)
        if not values:
            print(f"| `{path.name}` | 0 | - | - | - | - |")
            continue
        p50 = quantile(values, 0.50)
        p95 = quantile(values, 0.95)
        p99 = quantile(values, 0.99)
        maximum = max(values)
        print(
            f"| `{path.name}` | {len(values)} | {p50:.2f} | {p95:.2f} | "
            f"{p99:.2f} | {maximum:.2f} |"
        )
        per_file.append((path, len(values), p50, p95, p99, maximum))

        match = NAME_RE.match(path.name)
        if match:
            grouped[(match.group("config"), int(match.group("vus")))].append(p95)

    if grouped:
        print("\nMedian of per-run p95 values (one row per config and VU level):\n")
        print("| Config | VUs | Runs | Median p95 (ms) |")
        print("|---|---:|---:|---:|")
        medians: dict[tuple[str, int], float] = {}
        for key in sorted(grouped):
            config, vus = key
            median_p95 = statistics.median(grouped[key])
            medians[key] = median_p95
            print(f"| {config} | {vus} | {len(grouped[key])} | {median_p95:.2f} |")

        print("\nOverhead against the plaintext baseline (H1):\n")
        print("| VUs | Baseline p95 | Target p95 | Overhead |")
        print("|---:|---:|---:|---:|")
        for (config, vus) in sorted(medians):
            if config != "A":
                continue
            baseline = medians[(config, vus)]
            for target in ("D", "D-lab"):
                candidate = medians.get((target, vus))
                if candidate is None:
                    continue
                overhead = (candidate - baseline) / baseline * 100 if baseline else float("nan")
                print(
                    f"| {vus} | {baseline:.2f} | {candidate:.2f} | {overhead:+.2f}% |"
                )


if __name__ == "__main__":
    main()
