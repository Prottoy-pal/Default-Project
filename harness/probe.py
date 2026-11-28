"""harness/probe.py — send probes, one namespace at a time.

A probe description comes from expected.yaml. This module turns it into one or
more concrete packets, runs each in a child process inside the source
namespace, and returns a verdict per (probe, family, port).

Nothing here decides pass or fail. That is score.py's job, because a verdict
needs the expectation, and expectations live in the scenario.
"""

from __future__ import annotations

import json
from pathlib import Path

import common

HELPER = Path(__file__).resolve().parent / "_probe_helper.py"
PORT_PROBES = {"tcp", "udp"}


def expand(probe):
    """Yield (proto, family, port) for every packet this probe needs."""
    proto = probe["proto"]
    families = [f for f in ("ipv4", "ipv6") if f in probe["expect"]]
    if proto in PORT_PROBES:
        dports = probe["dport"]
        ports = dports if isinstance(dports, list) else [dports]
        for family in families:
            for port in ports:
                yield proto, family, port
    else:
        for family in families:
            yield proto, family, None


def send(topo, probe, proto, family, port):
    src = common.resolve(topo, probe["src"])
    dst = common.resolve(topo, probe["dst"])
    timeout = topo.get("timeouts", {}).get(
        "icmp6_nd_ms" if proto == "icmp6-nd"
        else "icmp_ms" if proto == "icmp-echo"
        else "tcp_connect_ms" if proto == "tcp"
        else "udp_reply_ms",
        1500,
    )
    spec = {
        "proto": proto,
        "family": family,
        "src": src[family],
        "dst": dst[family],
        "port": port,
        "timeout_ms": timeout,
        "iface": src["iface"],
    }
    r = common.sh(
        ["python3", str(HELPER), json.dumps(spec)],
        ns=src["ns"],
        timeout=(timeout / 1000.0) + 15,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return {
            "observed": "error",
            "latency_ms": 0,
            "resolution": "n/a",
            "detail": (r.stderr or "helper produced no output").strip()[:500],
        }
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        return {
            "observed": "error",
            "latency_ms": 0,
            "resolution": "n/a",
            "detail": f"unparseable helper output: {exc}",
        }


def run_all(topo, probes):
    """Return one row per packet, in declaration order."""
    rows = []
    for probe in probes:
        for proto, family, port in expand(probe):
            result = send(topo, probe, proto, family, port)
            rows.append({
                "id": probe["id"],
                "tier": probe.get("tier", "specified"),
                "proto": proto,
                "family": family,
                "port": port,
                "expected": probe["expect"][family],
                "observed": result["observed"],
                "verdict": ("error" if result["observed"] == "error"
                            else "pass" if result["observed"] == probe["expect"][family]
                            else "fail"),
                "resolution": result.get("resolution", "n/a"),
                "latency_ms": result.get("latency_ms", 0),
                "detail": result.get("detail", ""),
            })
    return rows
