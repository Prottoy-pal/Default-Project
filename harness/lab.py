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
SINKLOG = STATE / "sink.log"


def _ns(name):
    return ["ip", "netns", name]


def _step(argv, what):
    r = common.sh(argv)
    if r.returncode != 0:
        raise SystemExit(f"FAILED: {what}\n  cmd: {' '.join(argv)}\n  err: {r.stderr.strip()}")


def stop_sink():
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.2)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        PIDFILE.unlink(missing_ok=True)


def start_sink(topo):
    STATE.mkdir(parents=True, exist_ok=True)
    spec = json.dumps(topo.get("services", {}))
    log = SINKLOG.open("w")
    proc = subprocess.Popen(
        ["ip", "netns", "exec", common.DUT_NS, "python3", str(SINK), spec],
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    time.sleep(1.0)
    if proc.poll() is not None:
        raise SystemExit(f"sink died:\n{SINKLOG.read_text()}")
    PIDFILE.write_text(str(proc.pid))
    return proc.pid


def down(topo):
    stop_sink()
    for ns in topo["namespaces"]:
        common.sh(_ns(ns) + ["delete"])


def up(topo):
    down(topo)

    for ns in topo["namespaces"]:
        _step(_ns(ns) + ["add"], f"create namespace {ns}")

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

    start_sink(topo)
    time.sleep(0.3)


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
        raise SystemExit("run with sudo: network namespaces need CAP_SYS_ADMIN")

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
