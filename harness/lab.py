"""harness/lab.py — build, reset and tear down the lab from bench/topology.yaml.

    sudo python3 harness/lab.py up
    sudo python3 harness/lab.py reset
    sudo python3 harness/lab.py down
    sudo python3 harness/lab.py status

"Reset" is not a convenience. A run that inherits a chain, an address, or a
neighbour entry from a previous configuration is not measuring the
configuration it claims to measure.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import common

SINK = Path(__file__).resolve().parent / "_sink.py"
STATE = Path("/tmp/halffirewall")
PIDFILE = STATE / "sink.pid"


def _ns(action, name):
    """`ip netns add NAME` / `ip netns delete NAME`.

    Not to be confused with `ip -n NAME <command>`, which addresses a
    namespace that already exists.
    """
    return ["ip", "netns", action, name]


def _die(msg):
    """Exit 2: the harness failed, not the configuration under test."""
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def _step(argv, what):
    r = common.sh(argv)
    if r.returncode != 0:
        _die(f"FAILED: {what}\n  cmd: {' '.join(argv)}\n  err: {r.stderr.strip()}")


def stop_sink():
    if PIDFILE.exists():
        for line in PIDFILE.read_text().split():
            try:
                os.kill(int(line), signal.SIGTERM)
            except (ValueError, ProcessLookupError, PermissionError):
                pass
        time.sleep(0.5)
        PIDFILE.unlink(missing_ok=True)


def start_sink(topo):
    """Start the service sink in every namespace, not just the DUT.

    Forwarding probes target a peer (`dst: wan` or `dst: admin`). A TCP packet
    to a peer with no listener is answered with a RST, which the probe already
    reads as "the packet arrived". A UDP packet gets an ICMP port-unreachable,
    and whether that error makes it back depends on conntrack and the return
    path - too fragile to build the oracle on. A sink in every namespace means
    a forwarded packet is answered with a real reply, so `allow` and `drop` are
    decided by the ruleset alone.
    """
    STATE.mkdir(parents=True, exist_ok=True)
    spec = json.dumps(topo.get("services", {}))
    procs = []
    for ns in topo["namespaces"]:
        log = (STATE / f"sink-{ns}.log").open("w")
        proc = subprocess.Popen(
            ["ip", "netns", "exec", ns, "python3", str(SINK), spec],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        procs.append((ns, proc))
    time.sleep(1.0)
    for ns, proc in procs:
        if proc.poll() is not None:
            _die(f"sink died in {ns}:\n{(STATE / f'sink-{ns}.log').read_text()}")
    PIDFILE.write_text("\n".join(str(proc.pid) for _, proc in procs))
    return [proc.pid for _, proc in procs]


def down(topo):
    stop_sink()
    for ns in topo["namespaces"]:
        common.sh(_ns("delete", ns))


def up(topo):
    down(topo)

    for ns in topo["namespaces"]:
        _step(_ns("add", ns), f"create namespace {ns}")

    for link in topo["links"]:
        a, b = link["a"], link["b"]
        tmpa, tmpb = f"{link['name']}a", f"{link['name']}b"
        _step(["ip", "link", "add", tmpa, "type", "veth", "peer", "name", tmpb],
              f"create {link['name']}")
        _step(["ip", "link", "set", tmpa, "netns", a["ns"]],
              f"move {tmpa} -> {a['ns']}")
        _step(["ip", "link", "set", tmpb, "netns", b["ns"]],
              f"move {tmpb} -> {b['ns']}")
        _step(["ip", "-n", a["ns"], "link", "set", tmpa, "name", a["iface"]],
              f"rename {tmpa} -> {a['iface']}")
        _step(["ip", "-n", b["ns"], "link", "set", tmpb, "name", b["iface"]],
              f"rename {tmpb} -> {b['iface']}")

    # addresses
    for zone_name, zone in topo["zones"].items():
        ns = zone["ns"]
        for fam in ("ipv4", "ipv6"):
            spec = zone[fam]
            extra = ["nodad"] if fam == "ipv6" else []
            _step(["ip", "-n", ns, "addr", "add",
                   f"{spec['address']}/{spec['prefix']}", "dev", zone["iface"], *extra],
                  f"address {fam} on {zone_name}")

    for side, dut in topo["dut"].items():
        ns = common.DUT_NS
        for fam in ("ipv4", "ipv6"):
            spec = dut[fam]
            extra = ["nodad"] if fam == "ipv6" else []
            _step(["ip", "-n", ns, "addr", "add",
                   f"{spec['address']}/{spec['prefix']}", "dev", dut["iface"], *extra],
                  f"address {fam} on dut/{side}")

    # Kernel forwarding on the DUT. A scenario that says "this host does not
    # forward" is only testable if the kernel would otherwise forward; with
    # ip_forward=0 the packet dies before the forward hook and every such probe
    # passes for the wrong reason.
    fwd = topo.get("forwarding", {})
    for key, val in (fwd.get("sysctls") or {}).items():
        common.sh(["ip", "netns", "exec", fwd.get("ns", common.DUT_NS),
                   "sysctl", "-qw", f"{key}={val}"])

    # IPv6 housekeeping: no router advertisements, IPv6 definitely on
    for ns in topo["namespaces"]:
        for key, val in (("accept_ra", topo.get("ipv6", {}).get("accept_ra", 0)),
                         ("disable_ipv6", 0)):
            common.sh(["ip", "netns", "exec", ns, "sysctl", "-qw",
                       f"net.ipv6.conf.all.{key}={val}"])

    # links up
    for ns in topo["namespaces"]:
        _step(["ip", "-n", ns, "link", "set", "lo", "up"], f"lo up in {ns}")
        for iface in {z["iface"] for z in topo["zones"].values() if z["ns"] == ns} | \
                     {d["iface"] for d in topo["dut"].values() if ns == common.DUT_NS}:
            _step(["ip", "-n", ns, "link", "set", iface, "up"], f"{iface} up in {ns}")

    # Neighbour entries before the routes, so that the first probe on either
    # link does not depend on discovery succeeding.
    pin_neighbours(topo)

    # Peer routes: after the links are up, because a gateway is only
    # "reachable" while the interface that carries it is up.
    for ns, routes in (topo.get("routes") or {}).items():
        for fam, spec in routes.items():
            via = common.resolve(topo, spec["via"])[fam]
            _step(["ip", "-n", ns, "-6" if fam == "ipv6" else "-4",
                   "route", "add", spec["to"], "via", via],
                  f"route {ns} {fam} {spec['to']} via {via}")

    start_sink(topo)
    time.sleep(0.3)


def _mac(ns, iface):
    r = common.sh(["ip", "-n", ns, "-o", "link", "show", "dev", iface])
    parts = r.stdout.split()
    if "link/ether" not in parts:
        _die(f"cannot read the MAC of {iface} in {ns}: {r.stdout.strip()!r}")
    return parts[parts.index("link/ether") + 1]


def pin_neighbours(topo):
    """Give every link a permanent IPv6 neighbour entry, in both directions.

    Without this, a ruleset that drops ICMPv6 takes the whole second family
    down: the link never resolves, so every IPv6 allow-probe fails and every
    IPv6 drop-probe passes because nothing can be delivered at all. One defect
    (E) would then be recorded as a second, independent one (C), and the run
    would say nothing about the policy it claims to test.

    Permanent entries take resolution out of the path of the flow probes. The
    `icmp6-nd` probe deletes its own entry, solicits, and restores it, so
    whether the policy answers discovery is still measured - just no longer
    through every other probe.

    IPv4 is left alone: ARP is not matched by an `ip`/`inet` filter table, so a
    ruleset under test cannot break it the way it can break ICMPv6.
    """
    addr = {}
    for zone in topo["zones"].values():
        addr[(zone["ns"], zone["iface"])] = zone["ipv6"]["address"]
    for dut in topo["dut"].values():
        addr[(common.DUT_NS, dut["iface"])] = dut["ipv6"]["address"]

    for link in topo["links"]:
        ends = [link["a"], link["b"]]
        for here, there in (ends, ends[::-1]):
            target = addr[(there["ns"], there["iface"])]
            mac = _mac(there["ns"], there["iface"])
            _step(["ip", "-n", here["ns"], "-6", "neigh", "replace", target,
                   "lladdr", mac, "dev", here["iface"], "nud", "permanent"],
                  f"pin neighbour {target} in {here['ns']}/{here['iface']}")


def status(topo):
    out = {}
    for ns in topo["namespaces"]:
        r = common.sh(["ip", "-n", ns, "-brief", "addr"])
        out[ns] = r.stdout.strip()
    sink = PIDFILE.read_text().strip() if PIDFILE.exists() else None
    return {"namespaces": out, "sink_pid": sink}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["up", "down", "reset", "status"])
    ap.add_argument("--topology", default=None)
    args = ap.parse_args()

    topo = common.load_topology(args.topology)

    if os.geteuid() != 0:
        _die("run with sudo: network namespaces need CAP_SYS_ADMIN")

    if args.action == "up":
        up(topo)
        print(json.dumps(status(topo), indent=2))
    elif args.action == "down":
        down(topo)
        print("down")
    elif args.action == "reset":
        up(topo)
        print(json.dumps(status(topo), indent=2))
    else:
        print(json.dumps(status(topo), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
