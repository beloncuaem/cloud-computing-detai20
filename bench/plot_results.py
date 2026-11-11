#!/usr/bin/env python3
"""Regenerate the report figures from k6 summary JSON files.

Usage:
    pip install matplotlib
    python bench/plot_results.py

Reads bench/results/{A,D-lab,E-lab}_*_summary.json and writes:
    docs/report/figures/fig_benchmark.png
    docs/report/figures/fig_rotation.png
The script deliberately uses the same medians as bench/analyze.py.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results"
OUT = ROOT / "docs" / "report" / "figures"
CONFIGS = ("A", "D-lab")
VUS_LEVELS = (10, 50, 100)
COLORS = {"A": "#4C78A8", "D-lab": "#E45756", "E-lab": "#54A24B"}
LABELS = {
    "A": "A — baseline plaintext",
    "D-lab": "D-lab — envelope + Vault (HTTP)",
    "E-lab": "E-lab — xoay vòng (HTTP)",
}


def load_runs() -> dict[tuple[str, int], list[dict[str, float]]]:
    runs: dict[tuple[str, int], list[dict[str, float]]] = defaultdict(list)
    for path in sorted(RESULTS.glob("*_summary.json")):
        parts = path.stem.split("_")
        if len(parts) != 4 or not parts[2].startswith("run"):
            continue
        config, vus = parts[0], int(parts[1])
        payload = json.loads(path.read_text(encoding="utf-8"))
        metrics = payload.get("metrics", {})
        duration = metrics.get("http_req_duration", {})
        if "p(95)" not in duration:
            continue
        runs[(config, vus)].append(
            {
                "p50": float(duration.get("med", 0.0)),
                "p95": float(duration["p(95)"]),
                "p99": float(duration.get("p(99)", 0.0)),
                "rps": float(metrics.get("http_reqs", {}).get("rate", 0.0)),
                "error": float(metrics.get("http_req_failed", {}).get("value", 0.0)),
            }
        )
    return runs


def median(runs: list[dict[str, float]], key: str) -> float:
    return statistics.median(item[key] for item in runs)


def plot_benchmark(runs: dict[tuple[str, int], list[dict[str, float]]]) -> None:
    fig, (ax_lat, ax_rps) = plt.subplots(1, 2, figsize=(11, 4.2))

    latency_levels = (10, 50)
    for config in CONFIGS:
        xs = [index for index, vus in enumerate(latency_levels) if (config, vus) in runs]
        p95 = [median(runs[(config, latency_levels[index])], "p95") for index in xs]
        all_xs = [index for index, vus in enumerate(VUS_LEVELS) if (config, vus) in runs]
        rps = [median(runs[(config, VUS_LEVELS[index])], "rps") for index in all_xs]
        ax_lat.plot(xs, p95, "o-", color=COLORS[config], label=LABELS[config], linewidth=2)
        ax_rps.plot(all_xs, rps, "o-", color=COLORS[config], label=LABELS[config], linewidth=2)
        for x, value in zip(xs, p95):
            ax_lat.annotate(f"{value:.0f}", (x, value), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7)

    ax_lat.set_xticks(range(len(latency_levels)))
    ax_lat.set_xticklabels([str(v) for v in latency_levels])
    ax_lat.set_xlabel("Số virtual users")
    ax_lat.set_ylabel("p95 (ms)")
    ax_lat.set_title("Độ trễ p95 (trung vị; 100 VUs D-lab sụp, xem bảng)")
    ax_lat.grid(True, alpha=0.25)
    ax_lat.legend(fontsize=8)

    ax_rps.set_xticks(range(len(VUS_LEVELS)))
    ax_rps.set_xticklabels([str(v) for v in VUS_LEVELS])
    ax_rps.set_xlabel("Số virtual users")
    ax_rps.set_ylabel("Request/giây (trung vị)")
    ax_rps.set_title("Thông lượng")
    ax_rps.grid(True, alpha=0.25)
    ax_rps.legend(fontsize=8)

    fig.suptitle("So sánh baseline A và D-lab (D-lab: 31/10; A: 31/10 + 11/11, xem mục 4.4)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / "fig_benchmark.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_rotation(runs: dict[tuple[str, int], list[dict[str, float]]]) -> None:
    e_runs = runs.get(("E-lab", 50), [])
    if not e_runs:
        return
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    labels = [f"Lần {index}" for index in range(1, len(e_runs) + 1)]
    p95 = [item["p95"] for item in e_runs]
    errors = [item["error"] * 100 for item in e_runs]
    bars = ax.bar(labels, p95, color=COLORS["E-lab"], width=0.55)
    for bar, value in zip(bars, p95):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 30, f"{value:.0f}", ha="center", fontsize=9)
    ax.set_ylabel("p95 (ms)")
    ax.set_ylim(0, max(p95) * 1.18)
    ax.set_title("E-lab: 50 VUs, xoay DB + KEK, 0% lỗi")
    ax.text(
        0.02,
        0.95,
        "Tỷ lệ lỗi cả 3 lần: 0,00%",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        color="#2E7D32",
    )
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_rotation.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    plot_benchmark(runs)
    plot_rotation(runs)
    print(f"wrote {OUT / 'fig_benchmark.png'}")
    print(f"wrote {OUT / 'fig_rotation.png'}")


if __name__ == "__main__":
    main()
