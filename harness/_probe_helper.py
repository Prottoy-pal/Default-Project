"""harness/_probe_helper.py — executes ONE probe inside one network namespace.

Invoked by probe.py as:
    ip netns exec <src-ns> python3 _probe_helper.py '<json>'

It is a separate process on purpose: the namespace is entered by `ip netns
exec`, so this file never has to call setns(), and every probe starts from a
clean socket state.

Verdict vocabulary is fixed: allow | drop | error.
  allow — the packet reached the target host (even if the port refused it)
  drop  — no reply within the timeout
  error — the probe itself could not run; never recorded as a policy result
"""

from __future__ import annotations

import json
import math
import socket
import subprocess
import sys
import time


def tcp(spec):
    fam = socket.AF_INET6 if spec["family"] == "ipv6" else socket.AF_INET
    timeout = spec["timeout_ms"] / 1000.0
    start = time.monotonic()
    s = socket.socket(fam, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.bind((spec["src"], 0))
        rc = s.connect_ex((spec["dst"], spec["port"]))
    finally:
        s.close()
    latency = int((time.monotonic() - start) * 1000)
    # 0 = handshake completed. ECONNREFUSED = the packet arrived, the host
    # answered with RST. Both mean the firewall let it through.
    if rc in (0, 111, 61):
        return "allow", latency, f"connect_ex={rc}"
    if rc in (110, 60):  # ETIMEDOUT
        return "drop", latency, "connect timeout"
    return "drop", latency, f"connect_ex={rc}"


def udp(spec):
    fam = socket.AF_INET6 if spec["family"] == "ipv6" else socket.AF_INET
    timeout = spec["timeout_ms"] / 1000.0
    start = time.monotonic()
    s = socket.socket(fam, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.bind((spec["src"], 0))
        try:
            s.sendto(b"hf", (spec["dst"], spec["port"]))
        except OSError:
            return "drop", int((time.monotonic() - start) * 1000), "send failed"
        try:
            s.recvfrom(2048)
            return "allow", int((time.monotonic() - start) * 1000), "reply received"
        except socket.timeout:
            return "drop", int((time.monotonic() - start) * 1000), "no reply"
        except ConnectionRefusedError:
            # An ICMP port-unreachable came back. The datagram arrived and the
            # host said nothing is listening, which is the same evidence as a
            # TCP RST: the firewall let it through. Recording this as `error`
            # would fail a forwarding allow-probe against a peer that simply
            # has no listener, and the verdict would be about the lab, not the
            # ruleset.
            return "allow", int((time.monotonic() - start) * 1000), "icmp port unreachable"
    finally:
        s.close()


def icmp_echo(spec):
    secs = max(1, math.ceil(spec["timeout_ms"] / 1000))
    cmd = ["ping", "-c", "1", "-W", str(secs), "-I", spec["src"], spec["dst"]]
    if spec["family"] == "ipv6":
        cmd.insert(1, "-6")
    start = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=secs + 3)
    except FileNotFoundError:
        return "error", 0, "ping not installed (apt install iputils-ping)"
    except subprocess.TimeoutExpired:
        return "drop", int((time.monotonic() - start) * 1000), "ping hung"
    latency = int((time.monotonic() - start) * 1000)
    if r.returncode == 0:
        return "allow", latency, "echo reply"
    if "unreachable" in (r.stdout + r.stderr).lower():
        return "drop", latency, "destination unreachable"
    return "drop", latency, f"ping rc={r.returncode}"


def _neigh_lladdr(dst, iface):
    r = subprocess.run(["ip", "-6", "neigh", "show", dst, "dev", iface],
                       capture_output=True, text=True)
    parts = (r.stdout or "").split()
    if "lladdr" in parts:
        return parts[parts.index("lladdr") + 1]
    return None


def icmp6_nd(spec):
    """Neighbour discovery: solicit, and see whether the policy answers.

    The lab pins a permanent neighbour entry for every peer so that the flow
    probes do not depend on discovery. This probe removes its own entry first,
    because a pinned entry would make the ping succeed whether or not the
    policy answers the solicitation - which is the only thing it is here to
    measure. The entry is restored in a finally block, so a failed probe cannot
    leak into the probes that follow.

    resolution=ok tells score.py that this failure is not class E, and
    resolution=failed tells it that it is.
    """
    dst, iface = spec["dst"], spec.get("iface", "")
    lladdr = _neigh_lladdr(dst, iface)
    if lladdr:
        subprocess.run(["ip", "-6", "neigh", "del", dst, "dev", iface],
                       capture_output=True, text=True)
    try:
        observed, latency, detail = icmp_echo(spec)
        neigh = subprocess.run(["ip", "-6", "neigh", "show", dst, "dev", iface],
                               capture_output=True, text=True)
        out = (neigh.stdout or "").upper()
        resolved = any(state in out
                       for state in ("REACHABLE", "STALE", "DELAY", "PROBE"))
        if observed == "allow" and resolved:
            return "allow", latency, "neighbour resolved"
        if observed == "allow" and not resolved:
            return "allow", latency, "reply arrived but no neighbour entry"
        return "drop", latency, f"nd failed (neigh: {out.strip() or 'empty'})"
    finally:
        if lladdr:
            subprocess.run(["ip", "-6", "neigh", "replace", dst, "lladdr", lladdr,
                            "dev", iface, "nud", "permanent"],
                           capture_output=True, text=True)


HANDLERS = {
    "tcp": tcp,
    "udp": udp,
    "icmp-echo": icmp_echo,
    "icmp6-nd": icmp6_nd,
}


def main():
    spec = json.loads(sys.argv[1])
    handler = HANDLERS.get(spec["proto"])
    if handler is None:
        print(json.dumps({"observed": "error", "latency_ms": 0,
                          "resolution": "n/a",
                          "detail": f"unknown proto {spec['proto']!r}"}))
        return 0
    try:
        observed, latency, detail = handler(spec)
    except Exception as exc:  # noqa: BLE001 - a probe must never crash the run
        observed, latency, detail = "error", 0, f"{type(exc).__name__}: {exc}"
    resolution = "n/a"
    if spec["proto"] == "icmp6-nd":
        resolution = "ok" if observed == "allow" else "failed"
    print(json.dumps({
        "observed": observed,
        "latency_ms": latency,
        "resolution": resolution,
        "detail": detail,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
