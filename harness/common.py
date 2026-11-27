"""harness/common.py — shared helpers: topology, address resolution, subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOPOLOGY = REPO / "bench" / "topology.yaml"
DUT_NS = "fw"


def load_topology(path=None):
    """Parse bench/topology.yaml. Requires python3-yaml."""
    import yaml

    p = Path(path) if path else TOPOLOGY
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def endpoints(topo):
    """All names a scenario may use, so a typo fails loudly and early."""
    names = set(topo["zones"]) | {"loopback"}
    names |= {f"dut-{side}" for side in topo["dut"]}
    return names


def resolve(topo, name):
    """Map a scenario endpoint name to {ns, iface, ipv4, ipv6}."""
    if name == "loopback":
        return {"ns": DUT_NS, "iface": "lo", "ipv4": "127.0.0.1", "ipv6": "::1"}

    if name in topo["zones"]:
        z = topo["zones"][name]
        return {
            "ns": z["ns"],
            "iface": z["iface"],
            "ipv4": z["ipv4"]["address"],
            "ipv6": z["ipv6"]["address"],
        }

    if name.startswith("dut-"):
        side = name[4:]
        if side not in topo["dut"]:
            raise KeyError(f"{name!r}: the DUT has no side {side!r}")
        d = topo["dut"][side]
        return {
            "ns": DUT_NS,
            "iface": d["iface"],
            "ipv4": d["ipv4"]["address"],
            "ipv6": d["ipv6"]["address"],
        }

    raise KeyError(
        f"unknown endpoint {name!r}; known: {', '.join(sorted(endpoints(topo)))}"
    )


def sh(argv, *, ns=None, input_text=None, timeout=60):
    """Run a command, optionally inside a network namespace."""
    cmd = ["ip", "netns", "exec", ns, *argv] if ns else list(argv)
    return subprocess.run(
        cmd, input=input_text, capture_output=True, text=True, timeout=timeout
    )
