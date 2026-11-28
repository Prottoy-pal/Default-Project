"""harness/_sink.py — the services the lab probes against.

Started inside every namespace by lab.py, so a probe against the DUT and a
forwarding probe against a peer are both answered the same way. Opens one
listener per declared port, on both address families, and either
accepts-and-closes (TCP) or echoes one byte (UDP). No protocol is implemented
on purpose: the benchmark measures reachability, not the service.

Exit code 0 means every declared port bound successfully.
"""

from __future__ import annotations

import json
import socket
import selectors
import sys


def tcp_listeners(port):
    socks = []
    s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s4.bind(("0.0.0.0", port))
    s4.listen(64)
    s4.setblocking(False)
    socks.append(s4)
    try:
        s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s6.bind(("::", port))
        s6.listen(64)
        s6.setblocking(False)
        socks.append(s6)
    except OSError:
        pass
    return socks


def udp_listeners(port):
    socks = []
    s4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s4.bind(("0.0.0.0", port))
    s4.setblocking(False)
    socks.append(s4)
    try:
        s6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        s6.bind(("::", port))
        s6.setblocking(False)
        socks.append(s6)
    except OSError:
        pass
    return socks


def main():
    spec = json.loads(sys.argv[1])
    sel = selectors.DefaultSelector()
    kind = {}
    failed = []
    sel_error = []

    for port in spec.get("tcp", []):
        try:
            for s in tcp_listeners(port):
                sel.register(s, selectors.EVENT_READ)
                kind[s.fileno()] = "tcp"
        except OSError as exc:
            failed.append(f"tcp/{port}: {exc}")

    for port in spec.get("udp", []):
        try:
            for s in udp_listeners(port):
                sel.register(s, selectors.EVENT_READ)
                kind[s.fileno()] = "udp"
        except OSError as exc:
            failed.append(f"udp/{port}: {exc}")

    if failed:
        print(json.dumps({"failed": failed}), file=sys.stderr, flush=True)
        return 1

    print(json.dumps({"listening": spec}), flush=True)

    while True:
        try:
            events = sel.select(timeout=1.0)
        except OSError:
            continue
        for key, _ in events:
            sock = key.fileobj
            try:
                if kind[sock.fileno()] == "tcp":
                    conn, _addr = sock.accept()
                    conn.close()
                else:
                    data, addr = sock.recvfrom(2048)
                    sock.sendto(b"hf", addr)
            except OSError as exc:
                sel_error.append(str(exc))


if __name__ == "__main__":
    sys.exit(main())
