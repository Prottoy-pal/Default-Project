"""harness/apply.py — load a candidate ruleset into the DUT namespace.

Two rules that matter more than the code:

1. The ruleset is piped on stdin, not passed as a path. A generated file may
   live anywhere, and `nft -f -` keeps the DUT from reading the host's
   filesystem.
2. Nothing is flushed on the model's behalf. If a configuration relies on a
   previous state, that is part of what is being measured.
"""

from __future__ import annotations

import time

from common import DUT_NS, sh


def apply_text(text, ns=DUT_NS):
    start = time.monotonic()
    r = sh(["nft", "-f", "-"], ns=ns, input_text=text, timeout=60)
    return {
        "loaded": r.returncode == 0,
        "returncode": r.returncode,
        "stderr": (r.stderr or "").strip()[:4000],
        "duration_ms": int((time.monotonic() - start) * 1000),
    }


def apply_file(path, ns=DUT_NS):
    with open(path, encoding="utf-8") as fh:
        return apply_text(fh.read(), ns=ns)


def current_ruleset(ns=DUT_NS):
    """The ruleset actually loaded, for the record. Empty string on failure."""
    r = sh(["nft", "list", "ruleset"], ns=ns)
    return r.stdout if r.returncode == 0 else ""
