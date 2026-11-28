"""harness/score.py — apply, probe, compare, classify. One scenario, one JSON row.

    sudo python3 harness/score.py --scenario bench/scenarios/01-ssh-bastion \
         --config bench/scenarios/01-ssh-bastion/expert.nft \
         --out results/expert-01.json

Exit codes
    0  every probe matched its expectation
    1  at least one probe disagreed
    2  the harness itself failed (bad scenario, unknown endpoint, lab error)
        A 2 is never recorded as a model failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import apply as apply_mod
import common
import lab
import probe as probe_mod

INET = re.compile(r"\btable\s+inet\b")
IP6_TABLE = re.compile(r"\btable\s+ip6\b")
IP_TABLE = re.compile(r"\btable\s+ip\b(?!6)")
VERDICT_WORDS = re.compile(r"\b(accept|drop|reject)\b")
V4_MATCH = re.compile(r"\bip\s+(saddr|daddr|protocol)\b")
V6_MATCH = re.compile(r"\bip6\s+(saddr|daddr|protocol)\b")
ICMP_V4 = re.compile(r"\bicmp\s+\w")
ICMP_V6 = re.compile(r"\bicmpv6\s+\w")


def read_yaml(path):
    import yaml

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def strip_comments(text):
    """Remove nft comments before any structural heuristic runs.

    A comment is not configuration. Without this, a file whose header explains
    "`table inet` + policy accept" is classified as if it contained that table,
    and a model that writes its reasoning in comments would be scored on the
    reasoning. The hash still covers the original text.
    """
    out = []
    for line in text.splitlines():
        cut = line.find("#")
        out.append(line if cut < 0 else line[:cut])
    return "\n".join(out)


def heuristics(text):
    code = strip_comments(text)
    return {
        "has_inet": bool(INET.search(code)),
        "has_ip6_table": bool(IP6_TABLE.search(code)),
        "has_ip_table": bool(IP_TABLE.search(code)),
        "rule_count": len(VERDICT_WORDS.findall(code)),
        "v4_matches": len(V4_MATCH.findall(code)),
        "v6_matches": len(V6_MATCH.findall(code)),
        "icmp_v4": len(ICMP_V4.findall(code)),
        "icmp_v6": len(ICMP_V6.findall(code)),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def classify(rows, heur, loaded=True):
    """Execution-derived defect classes, named in bench/scenarios/README.md."""
    # A ruleset that never loaded produced no behaviour, so there is nothing to
    # classify. Saying "B" here would mean inferring a fail-open policy from a
    # file the kernel rejected - the probes all read "not-loaded" precisely
    # because nothing was tested. S is not a sixth defect class in the A-E
    # sense; it is a precondition failure, and the paper reports it as its own
    # column so that syntax errors do not silently inflate the prevalence of
    # the classes the project actually studies.
    if not loaded:
        return ["S"]

    v6 = [r for r in rows if r["family"] == "ipv6"]
    if not v6:
        return []

    allow_expect = [r for r in v6 if r["expected"] == "allow"]
    drop_expect = [r for r in v6 if r["expected"] == "drop"]
    # The neighbour-discovery probe is excluded from the C/D computation. Its
    # failure is evidence of E, not of over-blocking: a host that drops ICMPv6
    # discovery is unreachable by discovery, but that says nothing about whether
    # the policy over-blocks a flow. Without this, the one failing ND probe
    # would be counted as an allow->drop, every discovery-breaking ruleset would
    # also report C, and the E control would report C and E at once.
    allow_fail = [r for r in allow_expect
                  if r["verdict"] == "fail" and r["proto"] != "icmp6-nd"]
    drop_fail = [r for r in drop_expect
                 if r["verdict"] == "fail" and r["proto"] != "icmp6-nd"]

    defects = []

    # Fail-open: traffic that should have been dropped reached the host.
    # Over-block: traffic that should have been allowed never arrived.
    #
    # A and B are structural: if the configuration has no IPv6 filtering at all
    # (`table ip` alone, or a split `ip`/`ip6` pair whose v6 chain is empty),
    # the execution data looks exactly like D - the second family is wide open.
    # Naming it D would blame the default policy for a missing table, so the
    # structure decides A/B and the behaviour decides C/D.
    fail_open = bool(drop_fail)
    over_block = bool(allow_fail)

    if fail_open or over_block:
        if not heur["has_inet"] and not heur["has_ip6_table"]:
            defects.append("A")
        elif heur["has_ip6_table"] and not heur["has_inet"]:
            defects.append("B")
        else:
            if fail_open:
                defects.append("D")
            if over_block:
                defects.append("C")

    # ICMPv6 mishandling: neighbour discovery failed
    nd = [r for r in rows if r["proto"] == "icmp6-nd" and r["verdict"] == "fail"]
    if nd and any(r["resolution"] == "failed" for r in nd):
        defects.append("E")

    # keep order stable and unique
    return sorted(set(defects))


def tier_verdict(rows, tier):
    subset = [r for r in rows if r["tier"] == tier]
    if not subset:
        return None
    return "pass" if all(r["verdict"] == "pass" for r in subset) else "fail"


def family_verdict(rows, family):
    subset = [r for r in rows if r["family"] == family]
    if not subset:
        return None
    return "pass" if all(r["verdict"] == "pass" for r in subset) else "fail"


def summarise(rows, loaded=True):
    if not loaded:
        return {
            "ipv4": "not-loaded",
            "ipv6": "not-loaded",
            "parity": "not-loaded",
            "specified": "not-loaded",
            "silent": "not-loaded",
            "passed": 0,
            "total": len(rows),
        }
    v4, v6 = family_verdict(rows, "ipv4"), family_verdict(rows, "ipv6")
    parity = "pass" if v4 == "pass" and v6 == "pass" else "fail"
    return {
        "ipv4": v4,
        "ipv6": v6,
        "parity": parity,
        "specified": tier_verdict(rows, "specified"),
        "silent": tier_verdict(rows, "silent"),
        "passed": sum(1 for r in rows if r["verdict"] == "pass"),
        "total": len(rows),
    }


def _die(msg):
    """Exit 2: the harness failed, not the configuration under test."""
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def validate(scenario, expected, topo):
    known = common.endpoints(topo)
    problems = []
    for p in expected["probes"]:
        for key in ("id", "proto", "src", "dst", "expect"):
            if key not in p:
                problems.append(f"probe {p.get('id', '?')}: missing {key}")
        for key in ("src", "dst"):
            if key in p and p[key] not in known:
                problems.append(f"probe {p.get('id')}: unknown {key} {p[key]!r}")
        if p.get("proto") in probe_mod.PORT_PROBES and "dport" not in p:
            problems.append(f"probe {p.get('id')}: tcp/udp needs dport")
        for fam, want in p.get("expect", {}).items():
            if fam not in ("ipv4", "ipv6"):
                problems.append(f"probe {p.get('id')}: bad family {fam!r}")
            if want not in ("allow", "drop"):
                problems.append(f"probe {p.get('id')}: bad expectation {want!r}")
    if problems:
        _die("scenario invalid:\n  " + "\n  ".join(problems))
    if not expected.get("probes"):
        _die(f"{scenario}: expected.yaml declares no probes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--condition", default="expert")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--model", default="expert-config")
    ap.add_argument("--reset", action="store_true", help="rebuild the lab first")
    ap.add_argument("--keep", action="store_true", help="leave the lab running")
    ap.add_argument("--topology", default=None)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("run with sudo", file=sys.stderr)
        return 2

    scenario_dir = Path(args.scenario).resolve()
    if not scenario_dir.is_dir():
        print(f"not a scenario directory: {scenario_dir}", file=sys.stderr)
        return 2

    policy = read_yaml(scenario_dir / "policy.yaml")
    expected = read_yaml(scenario_dir / "expected.yaml")
    topo = common.load_topology(args.topology)
    validate(scenario_dir, expected, topo)

    if args.reset:
        print("building the lab ...", file=sys.stderr)
        lab.up(topo)

    text = Path(args.config).read_text(encoding="utf-8")
    applied = apply_mod.apply_text(text)

    if applied["loaded"]:
        rows = probe_mod.run_all(topo, expected["probes"])
    else:
        # A ruleset that will not load protects nothing: failure on both
        # families, recorded with the reason rather than hidden.
        rows = []
        for p in expected["probes"]:
            for proto, family, port in probe_mod.expand(p):
                rows.append({
                    "id": p["id"], "tier": p.get("tier", "specified"),
                    "proto": proto, "family": family, "port": port,
                    "expected": p["expect"][family], "observed": "not-loaded",
                    "verdict": "fail", "resolution": "n/a",
                    "latency_ms": 0, "detail": "ruleset failed to load",
                })

    heur = heuristics(text)
    loaded = applied["loaded"]

    # An `error` means the probe itself could not run - a missing binary, a
    # socket the namespace refused, a helper that crashed. It is not evidence
    # about the ruleset, so it must not be counted as a pass or a failure. The
    # contract in harness/README.md is that it fails the run; the row is not
    # written, and the cell is retried rather than recorded.
    errors = [r for r in rows if r["verdict"] == "error"]
    if errors:
        for r in errors[:5]:
            print(f"  probe error: {r['id']} {r['family']} - {r['detail']}",
                  file=sys.stderr)
        _die(f"{len(errors)} probe(s) could not be executed; no row written")

    verdicts = summarise(rows, loaded)
    defects = classify(rows, heur, loaded)

    row = {
        "run_id": (f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}"
                   f"__{policy['id']}__{args.condition}__{args.model}__r{args.repeat}"),
        "scenario": policy["id"],
        "family": policy.get("family"),
        "variant": policy.get("variant"),
        "condition": args.condition,
        "repeat": args.repeat,
        "model": {"provider": "", "name": args.model, "tag": "", "temperature": 0.0},
        "generation": {
            "prompt_sha256": hashlib.sha256(policy["prompt"].encode()).hexdigest(),
            "raw_output": "",
            "extracted_ruleset": text,
        },
        "apply": {"loaded": applied["loaded"], "stderr": applied["stderr"],
                  "duration_ms": applied["duration_ms"]},
        "load_failure": not applied["loaded"],
        "probes": rows,
        "verdicts": verdicts,
        "defects": defects,
        "heuristics": heur,
        "host": {"hostname": socket.gethostname(), "kernel": platform.release(),
                 "kernel_version": platform.version()},
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    out = Path(args.out) if args.out else \
        common.REPO / "results" / f"{row['run_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(row, indent=2), encoding="utf-8")

    # ---------------- human output ----------------
    print(f"\n{policy['id']}  ·  {args.condition}  ·  {args.model}\n")
    print(f"  apply      {'OK' if applied['loaded'] else 'FAILED'}"
          f"  ({applied['duration_ms']} ms)")
    if not applied["loaded"]:
        for line in applied["stderr"].splitlines()[:6]:
            print(f"             {line}")
        print(f"  no probes executed: the ruleset did not load")
    else:
        for r in rows:
            mark = "PASS" if r["verdict"] == "pass" else "FAIL"
            target = f":{r['port']}" if r["port"] else ""
            print(f"  {mark}  {r['id']:<28} {r['proto']}{target:<7} {r['family']:<5}"
                  f" expected={r['expected']:<5} observed={r['observed']}")

    print(f"\n  ipv4={verdicts['ipv4']}  ipv6={verdicts['ipv6']}"
          f"  parity={verdicts['parity']}")
    print(f"  specified={verdicts['specified']}  silent={verdicts['silent']}")
    print(f"  defects={defects or 'none'}")
    print(f"  {verdicts['passed']}/{verdicts['total']} probes matched")
    print(f"  row -> {out}\n")

    if not args.keep and args.reset:
        lab.down(topo)

    return 0 if verdicts["parity"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
