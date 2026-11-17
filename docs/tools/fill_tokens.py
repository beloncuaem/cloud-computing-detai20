#!/usr/bin/env python3
"""Fill benchmark tokens in the report markdown and the slide JSON.

Reads k6 results from bench/results, reuses bench/analyze.py parsing, and
replaces @@TOKEN@@ in docs/report/bao-cao-ky-thuat.md and {{TOKEN}} in
docs/slides/noid-dung-slide.json with measured values (Vietnamese number
format: comma decimal, dot thousands). Tokenized backups are kept in %TEMP%.

Run AFTER the measurement matrix finishes:
    python -X utf8 docs/tools/fill_tokens.py
"""

from __future__ import annotations

import json
import shutil
import statistics
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "bench"))
import analyze  # noqa: E402

REPORT_MD = REPO_ROOT / "docs" / "report" / "bao-cao-ky-thuat.md"
SLIDE_JSON = REPO_ROOT / "docs" / "slides" / "noid-dung-slide.json"
KICH_BAN = REPO_ROOT / "docs" / "slides" / "kich-ban-thuyet-trinh.md"
RESULTS = REPO_ROOT / "bench" / "results"

# report/slide token prefix -> result-file config name
CFG = {"B": "B", "D": "D", "DP": "Dprime", "E": "E"}
VUS = (10, 50, 100)
SAT_P95_MS = 50000.0   # k6 timeout is 60 s; a collapsed level sits near it
SAT_ERR = 0.05         # >=5% failed requests => saturated, excluded from H1


def vn(x: float, dec: int = 2) -> str:
    """Vietnamese number: 1,140.35 -> 1.140,35."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x: float, dec: int = 2, sign: bool = False) -> str:
    s = f"{x:+,.{dec}f}" if sign else f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".") + "%"


def load():
    runs, summaries = {}, {}
    for path in sorted(RESULTS.glob("*")):
        m = analyze.CSV_RE.match(path.name)
        if m:
            stats = analyze.stats_from_csv(path)
        else:
            m = analyze.SUMMARY_RE.match(path.name)
            stats = analyze.stats_from_summary(path) if m else None
        if not m or stats is None:
            continue
        key = (m.group("config"), int(m.group("vus")), int(m.group("run")))
        if stats.source == "summary":
            summaries[key] = stats
        old = runs.get(key)
        if old is None or (old.source == "summary" and stats.source == "csv"):
            runs[key] = stats
    for key, stats in runs.items():
        s = summaries.get(key)
        if s is not None:
            stats.rps = s.rps
            stats.error_rate = s.error_rate
    grouped = defaultdict(list)
    for (cfg, vus, _run), stats in runs.items():
        grouped[(cfg, vus)].append(stats)
    return grouped


def median_of(grouped, cfg, vus, attr):
    vals = [getattr(s, attr) for s in grouped.get((cfg, vus), [])
            if getattr(s, attr) == getattr(s, attr)]
    return statistics.median(vals) if vals else float("nan")


def main() -> None:
    grouped = load()
    med, err, sat = {}, {}, {}
    for tok, cfg in CFG.items():
        for v in VUS:
            med[(tok, v)] = {
                "RPS": median_of(grouped, cfg, v, "rps"),
                "P50": median_of(grouped, cfg, v, "p50"),
                "P95": median_of(grouped, cfg, v, "p95"),
                "P99": median_of(grouped, cfg, v, "p99"),
            }
            errs = [s.error_rate for s in grouped.get((cfg, v), [])
                    if s.error_rate == s.error_rate]
            err[(tok, v)] = max(errs) if errs else float("nan")
            sat[(tok, v)] = (med[(tok, v)]["P95"] >= SAT_P95_MS
                             or err[(tok, v)] >= SAT_ERR)

    def overhead(target, v):
        b, t = med[("B", v)]["P95"], med[(target, v)]["P95"]
        if sat[("B", v)] or sat[(target, v)] or not b:
            return None
        return (t - b) / b * 100

    tokens = {}
    for tok in CFG:
        for v in VUS:
            for metric in ("RPS", "P50", "P95", "P99"):
                tokens[f"{tok}_{metric}_{v}"] = vn(med[(tok, v)][metric])
            tokens[f"{tok}_ERR_{v}"] = pct(err[(tok, v)] * 100)
            tokens[f"ERR_{tok}_{v}"] = pct(err[(tok, v)] * 100)
    for v in VUS:
        for target, key in (("D", "H1_D"), ("DP", "H1_DP")):
            o = overhead(target, v)
            tokens[f"{key}_{v}"] = pct(o, sign=True) if o is not None else "n/a (bão hòa)"
        o = overhead("D", v)
        tokens[f"H1_{v}"] = pct(o, sign=True) if o is not None else "n/a (bão hòa)"

    # H1 conclusion over non-saturated levels, envelope without cache (D).
    d_ov = [overhead("D", v) for v in VUS if overhead("D", v) is not None]
    if d_ov and max(d_ov) <= 30:
        h1 = "đạt"
    elif d_ov and min(d_ov) <= 30:
        h1 = "đạt một phần"
    else:
        h1 = "không đạt"
    tokens["H1_KETLUAN"] = h1

    parts = []
    for v in VUS:
        o = overhead("D", v)
        parts.append(f"{pct(o, sign=True)} ở {v} VUs" if o is not None
                     else f"bão hòa ở {v} VUs")
    dp_parts = []
    for v in VUS:
        o = overhead("DP", v)
        if o is not None:
            dp_parts.append(f"{pct(o, sign=True)} ở {v} VUs")
    tokens["H1_DIENGIAI"] = (
        "Overhead p95 của D (envelope, không cache) so với baseline B là "
        + ", ".join(parts) + ". "
        + ("Với D' (cache DEK 120 s) overhead còn " + ", ".join(dp_parts) + ". "
           if dp_parts else "")
    )

    # H2: rotation continuity, config E.
    e_errs = [err[("E", v)] for v in VUS if not sat[("E", v)]]
    e_all = [err[("E", v)] for v in VUS]
    worst = max(e_all) if e_all else float("nan")
    tokens["H2_KETLUAN"] = "đạt" if (e_errs and max(e_errs) < 0.001) else "không đạt"
    tokens["H2_DIENGIAI"] = (
        f"E xoay credential DB ở giây 60 và xoay KEK trong cửa sổ đo; "
        f"tỷ lệ http_req_failed lớn nhất trên các mức không bão hòa là "
        f"{pct(max(e_errs) * 100) if e_errs else 'n/a'}, "
        f"toàn bộ các mức là {pct(worst * 100)}."
    )

    # Cache effect D vs Dprime.
    ce = []
    for v in VUS:
        c, w = med[("D", v)]["P95"], med[("DP", v)]["P95"]
        if sat[("D", v)] or sat[("DP", v)] or not c:
            continue
        ce.append(f"p95 {pct((w - c) / c * 100, sign=True)} ở {v} VUs")
    tokens["CACHE_EFFECT"] = (
        ("so với D, D' thay đổi " + ", ".join(ce) + ".") if ce
        else "không đủ mức không bão hòa để kết luận."
    )

    # Backup tokenized sources, then fill in place.
    backup = Path(tempfile.gettempdir()) / "detai20-token-backup"
    backup.mkdir(exist_ok=True)
    shutil.copy2(REPORT_MD, backup / REPORT_MD.name)
    shutil.copy2(SLIDE_JSON, backup / SLIDE_JSON.name)
    if KICH_BAN.exists():
        shutil.copy2(KICH_BAN, backup / KICH_BAN.name)

    md = REPORT_MD.read_text(encoding="utf-8")
    for key, val in tokens.items():
        md = md.replace(f"@@{key}@@", val)
    REPORT_MD.write_text(md, encoding="utf-8", newline="")

    if KICH_BAN.exists():
        kb = KICH_BAN.read_text(encoding="utf-8")
        for key, val in tokens.items():
            kb = kb.replace(f"@@{key}@@", val)
        KICH_BAN.write_text(kb, encoding="utf-8", newline="")

    data = json.loads(SLIDE_JSON.read_text(encoding="utf-8"))
    raw = json.dumps(data, ensure_ascii=False)
    for key, val in tokens.items():
        raw = raw.replace(f"{{{{{key}}}}}", val)
    SLIDE_JSON.write_text(json.dumps(json.loads(raw), ensure_ascii=False, indent=2),
                          encoding="utf-8", newline="")

    left_md = md.count("@@")
    left_js = raw.count("{{")
    left_kb = KICH_BAN.read_text(encoding="utf-8").count("@@") if KICH_BAN.exists() else 0
    print(f"filled {len(tokens)} token keys; remaining @@ md={left_md}, "
          f"{{{{ json={left_js}, @@ kich-ban={left_kb}")
    print("H1:", tokens["H1_KETLUAN"], "| H2:", tokens["H2_KETLUAN"])
    print("H1_DIENGIAI:", tokens["H1_DIENGIAI"])
    print("H2_DIENGIAI:", tokens["H2_DIENGIAI"])
    print("CACHE_EFFECT:", tokens["CACHE_EFFECT"])
    if left_md or left_js or left_kb:
        raise SystemExit("Unfilled tokens remain; check token names.")


if __name__ == "__main__":
    main()