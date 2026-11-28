"""scripts/analyze.py - rows in, report numbers out.

    python3 scripts/analyze.py results/
    python3 scripts/analyze.py results/ --json summary.json
    python3 scripts/analyze.py --selftest

Reads every results/*.json row that was produced by generate/run_models.py
(expert rows are skipped), groups by (model, condition), and prints:

  * cells, and parity rate with a Wilson 95% interval
  * IPv4 and IPv6 correctness separately - a parity number alone hides which
    family failed
  * silent-exposure rate: specified probes all pass AND at least one silent
    probe fails
  * fail-open and over-block packet counts

Wilson, not the normal approximation: with 18-54 cells per condition the
normal interval produces nonsense near 0% and 100%, which is exactly where
these proportions are expected to sit.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def pct(k, n):
    if n == 0:
        return "n/a"
    p, lo, hi = wilson(k, n)
    return f"{100 * p:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def load_rows(paths):
    rows = []
    for p in paths:
        try:
            row = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"skip {p}: {exc}", file=sys.stderr)
            continue
        if not row.get("probes"):
            continue
        if (row.get("model") or {}).get("name") == "expert-config":
            continue
        rows.append(row)
    return rows


def summarise(rows):
    groups = defaultdict(list)
    for row in rows:
        key = ((row.get("model") or {}).get("name", "?"), row.get("condition", "?"))
        groups[key].append(row)

    out = []
    for (model, condition), cells in sorted(groups.items()):
        # A ruleset the kernel rejected was never executed, so it cannot
        # contribute to a behavioural proportion. Counting it as a parity
        # failure would make "does not compile" look like "fails on IPv6",
        # which are different findings. It gets its own column and its own
        # denominator, and the parity rate is over cells that actually ran.
        total = len(cells)
        executed = [c for c in cells if not c.get("load_failure")]
        not_loaded = total - len(executed)
        n = len(executed)
        parity = sum(1 for c in executed if c["verdicts"]["parity"] == "pass")
        v4 = sum(1 for c in executed if c["verdicts"]["ipv4"] == "pass")
        v6 = sum(1 for c in executed if c["verdicts"]["ipv6"] == "pass")
        exposed = sum(
            1 for c in executed
            if c["verdicts"]["specified"] == "pass" and c["verdicts"]["silent"] == "fail"
        )
        fail_open = over_block = 0
        for c in executed:
            for p in c["probes"]:
                if p["verdict"] == "pass":
                    continue
                if p["expected"] == "drop" and p["observed"] in ("allow",):
                    fail_open += 1
                elif p["expected"] == "allow" and p["observed"] in ("drop",):
                    over_block += 1
        defects = defaultdict(int)
        for c in executed:
            for d in c.get("defects", []):
                defects[d] += 1
        out.append({
            "model": model,
            "condition": condition,
            "cells": total,
            "executed": n,
            "load_failed": not_loaded,
            "load_failure_rate": pct(not_loaded, total),
            "parity_pass": parity,
            "parity": pct(parity, n),
            "ipv4_pass": v4,
            "ipv6_pass": v6,
            "silent_exposed": exposed,
            "silent_exposure": pct(exposed, n),
            "fail_open_packets": fail_open,
            "over_block_packets": over_block,
            "defects": dict(sorted(defects.items())),
        })
    return out


def print_table(rows):
    if not rows:
        print("no model rows yet - run scripts/collect.sh first")
        return
    print(f"{'model':<26} {'cond':<5} {'cells':>5} {'exec':>4} {'load-fail':>9}  "
          f"{'parity':<22} {'v4':>4} {'v6':>4}  {'silent-exposed':<22} "
          f"{'fail-open':>9} {'over-block':>10}  defects")
    print("-" * 140)
    for r in rows:
        print(f"{r['model']:<26} {r['condition']:<5} {r['cells']:>5} {r['executed']:>4} "
              f"{r['load_failure_rate']:>9}  {r['parity']:<22} "
              f"{r['ipv4_pass']:>4} {r['ipv6_pass']:>4}  {r['silent_exposure']:<22} "
              f"{r['fail_open_packets']:>9} {r['over_block_packets']:>10}  "
              f"{r['defects'] or '-'}")
    print()
    print("cells = rows collected; exec = rows whose ruleset loaded. parity, ipv4,")
    print("ipv6 and silent-exposed are proportions over exec, with Wilson 95%")
    print("intervals. A row that did not load is counted under load-fail and never")
    print("as a parity failure: 'does not compile' and 'fails on IPv6' are different")


def selftest():
    ok = True

    p, lo, hi = wilson(0, 10)
    if not (p == 0 and lo == 0 and 0 < hi < 0.35):
        print(f"FAIL wilson(0,10) -> {(p, lo, hi)}")
        ok = False
    p, lo, hi = wilson(10, 10)
    if not (p == 1 and 0.65 < lo < 1 and hi == 1):
        print(f"FAIL wilson(10,10) -> {(p, lo, hi)}")
        ok = False
    p, lo, hi = wilson(5, 10)
    if not (abs(p - 0.5) < 1e-9 and lo < 0.5 < hi):
        print(f"FAIL wilson(5,10) -> {(p, lo, hi)}")
        ok = False

    def cell(parity, v4, v6, spec, sil, probes, defects=(), load_failure=False):
        return {
            "model": {"name": "local:test"},
            "condition": "C1",
            "verdicts": {"parity": parity, "ipv4": v4, "ipv6": v6,
                         "specified": spec, "silent": sil},
            "probes": probes,
            "defects": list(defects),
            "load_failure": load_failure,
        }

    good = {"verdict": "pass", "expected": "allow", "observed": "allow"}
    fo = {"verdict": "fail", "expected": "drop", "observed": "allow"}
    ob = {"verdict": "fail", "expected": "allow", "observed": "drop"}
    rows = [
        cell("pass", "pass", "pass", "pass", "pass", [good], ["C"]),
        cell("fail", "pass", "fail", "pass", "fail", [good, fo, ob], ["D"]),
        # A ruleset the kernel rejected: nothing was executed, so it must not
        # appear in any behavioural proportion or in the A-E tally.
        cell("not-loaded", "not-loaded", "not-loaded", "not-loaded", "not-loaded",
             [], ["S"], load_failure=True),
    ]
    s = summarise(rows)[0]
    checks = [
        (s["cells"] == 3, "cells"),
        (s["executed"] == 2, "executed excludes load failures"),
        (s["load_failed"] == 1, "load failures counted"),
        (s["parity_pass"] == 1, "parity count"),
        (s["silent_exposed"] == 1, "silent exposure counts specified-pass + silent-fail"),
        (s["fail_open_packets"] == 1, "fail-open"),
        (s["over_block_packets"] == 1, "over-block"),
        (s["defects"] == {"C": 1, "D": 1}, "defect tally excludes S"),
    ]
    for good_check, name in checks:
        if not good_check:
            print(f"FAIL {name}: {s}")
            ok = False

    print("selftest: " + ("ok" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", default="results")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    root = Path(args.results)
    paths = sorted(root.glob("*.json")) if root.is_dir() else [root]
    rows = summarise(load_rows(paths))
    print_table(rows)
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
