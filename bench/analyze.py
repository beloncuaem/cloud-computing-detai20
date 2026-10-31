#!/usr/bin/env python3
"""Summarize k6 CSV exports or summary JSON files into p50/p95/p99.

Usage:
    python bench/analyze.py "bench/results/*.csv"
    python bench/analyze.py "bench/results/*.csv.gz" "bench/results/*_summary.json"
    docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim \
        python bench/analyze.py "bench/results/*.csv.gz" "bench/results/*_summary.json"

The script uses only the Python standard library. It groups files by the
configuration, VU count and run encoded in the file name, for example:
    D-lab_50_run1.csv        -> config=D-lab, vus=50, run=1
    D-lab_50_run1.csv.gz     -> same (gzip-compressed raw CSV)
    D-lab_50_run1_summary.json -> same (k6 --summary-export)
If both a CSV and a summary JSON exist for one run, the CSV is used.
"""

from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

CSV_RE = re.compile(
    r"^(?P<config>[A-Za-z][A-Za-z0-9'-]*)_(?P<vus>\d+)_run(?P<run>\d+)(?:_summary)?\.csv(?:\.gz)?$"
)
SUMMARY_RE = re.compile(
    r"^(?P<config>[A-Za-z][A-Za-z0-9'-]*)_(?P<vus>\d+)_run(?P<run>\d+)_summary\.json$"
)


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


def read_csv_durations(path: Path) -> list[float]:
    values: list[float] = []
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", newline="", encoding="utf-8-sig") as handle:
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


@dataclass
class RunStats:
    source: str
    samples: int
    p50: float
    p95: float
    p99: float
    maximum: float
    rps: float = float("nan")
    error_rate: float = float("nan")


def stats_from_csv(path: Path) -> RunStats | None:
    values = read_csv_durations(path)
    if not values:
        return None
    return RunStats(
        source="csv",
        samples=len(values),
        p50=quantile(values, 0.50),
        p95=quantile(values, 0.95),
        p99=quantile(values, 0.99),
        maximum=max(values),
    )


def stats_from_summary(path: Path) -> RunStats | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    metrics = payload.get("metrics", {})
    duration = metrics.get("http_req_duration", {})
    p95 = duration.get("p(95)")
    if p95 is None:
        return None
    count = metrics.get("http_reqs", {}).get("count") or 0
    return RunStats(
        source="summary",
        samples=int(count),
        p50=float(duration.get("med", duration.get("p(50)", float("nan")))),
        p95=float(p95),
        p99=float(duration.get("p(99)", float("nan"))),
        maximum=float(duration.get("max", float("nan"))),
        rps=float(metrics.get("http_reqs", {}).get("rate", float("nan"))),
        error_rate=float(metrics.get("http_req_failed", {}).get("value", float("nan"))),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "patterns",
        nargs="*",
        default=[
            "bench/results/*.csv",
            "bench/results/*.csv.gz",
            "bench/results/*_summary.json",
        ],
        help="glob pattern(s) for k6 CSV or summary JSON exports",
    )
    args = parser.parse_args()

    files: list[Path] = []
    for pattern in args.patterns:
        files.extend(Path(p) for p in sorted(glob.glob(pattern)))
    files = list(dict.fromkeys(files))

    if not files:
        raise SystemExit(
            "No result files matched. Run k6 with --out csv=... or --summary-export=..."
        )

    runs: dict[tuple[str, int, int], RunStats] = {}
    summaries: dict[tuple[str, int, int], RunStats] = {}
    for path in files:
        match = CSV_RE.match(path.name)
        if match:
            stats = stats_from_csv(path)
        else:
            match = SUMMARY_RE.match(path.name)
            stats = stats_from_summary(path) if match else None
        if not match or stats is None:
            continue
        key = (match.group("config"), int(match.group("vus")), int(match.group("run")))
        if stats.source == "summary":
            summaries[key] = stats
        existing = runs.get(key)
        # Prefer raw CSV over a summary for the same run.
        if existing is None or (existing.source == "summary" and stats.source == "csv"):
            runs[key] = stats

    # A raw CSV has latencies but no request rate; take RPS/error from the
    # matching summary JSON when both were exported by the same k6 run.
    for key, stats in runs.items():
        summary = summaries.get(key)
        if summary is not None:
            stats.rps = summary.rps
            stats.error_rate = summary.error_rate

    if not runs:
        raise SystemExit("No readable k6 results found in matched files.")

    print(
        "| Config | VUs | Run | Source | Samples | RPS | p50 (ms) | p95 (ms) | "
        "p99 (ms) | max (ms) | Error |"
    )
    print("|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    grouped: dict[tuple[str, int], list[RunStats]] = defaultdict(list)
    for (config, vus, run), stats in sorted(runs.items()):
        print(
            f"| {config} | {vus} | {run} | {stats.source} | {stats.samples} | "
            f"{stats.rps:.2f} | {stats.p50:.2f} | {stats.p95:.2f} | {stats.p99:.2f} | "
            f"{stats.maximum:.2f} | {stats.error_rate * 100:.2f}% |"
        )
        grouped[(config, vus)].append(stats)

    print("\nMedian of per-run p95 values (one row per config and VU level):\n")
    print(
        "| Config | VUs | Runs | Median p50 (ms) | Median p95 (ms) | "
        "Median p99 (ms) | Median RPS | Max error |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    medians: dict[tuple[str, int], float] = {}
    for key in sorted(grouped):
        config, vus = key
        stats_list = grouped[key]
        median_p50 = statistics.median(item.p50 for item in stats_list)
        median_p95 = statistics.median(item.p95 for item in stats_list)
        median_p99 = statistics.median(item.p99 for item in stats_list)
        medians[key] = median_p95
        rates = [item.rps for item in stats_list if item.rps == item.rps]
        errors = [item.error_rate for item in stats_list if item.error_rate == item.error_rate]
        median_rps = statistics.median(rates) if rates else float("nan")
        max_error = max(errors) if errors else float("nan")
        print(
            f"| {config} | {vus} | {len(stats_list)} | {median_p50:.2f} | "
            f"{median_p95:.2f} | {median_p99:.2f} | {median_rps:.2f} | "
            f"{max_error * 100:.2f}% |"
        )

    print("\nOverhead against the plaintext baseline (H1):\n")
    print("| VUs | Baseline p95 | Target p95 | Overhead |")
    print("|---:|---:|---:|---:|")
    for config, vus in sorted(medians):
        if config != "A":
            continue
        baseline = medians[(config, vus)]
        for target in ("D", "D-lab"):
            candidate = medians.get((target, vus))
            if candidate is None:
                continue
            overhead = (candidate - baseline) / baseline * 100 if baseline else float("nan")
            print(f"| {vus} | {baseline:.2f} | {candidate:.2f} | {overhead:+.2f}% |")


if __name__ == "__main__":
    main()
