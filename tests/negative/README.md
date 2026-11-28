# Negative controls

Six configurations that are **deliberately wrong**, written so that the
oracle has something to fail against.

An oracle you have never seen fail is not an oracle. It is a set of assertions
that happen to pass.

| File | Defect | What it pretends to be | What it actually does |
|---|---|---|---|
| `a-ip-table-only.nft` | **A** | A careful IPv4 firewall | Filters IPv4 correctly and leaves IPv6 entirely unfiltered |
| `c-over-block.nft` | **C** | Strict, dual-stack | Locks the administrator out over IPv6 |
| `d-fail-open.nft` | **D** | Hardened | Leaves SSH and every other port open over IPv6 |
| `d-scoped-accept.nft` | **D** | Correct default-accept ruleset | Drops SSH from the untrusted zone over IPv4 only |
| `d-v4-only-negative.nft` | **D** | Correct default-accept ruleset with explicit refusals | Writes the refusal for IPv4 only, so IPv6 falls through to accept |
| `e-nd-blocked.nft` | **E** | Correct dual-stack ruleset | Refuses neighbour discovery; every flow rule is right |

Run them against their scenarios:

```bash
sudo bash harness/run.sh bench/scenarios/03-db-server \
     --config tests/negative/a-ip-table-only.nft --reset
# expect: exit 1, defects=[A], ipv4=pass, ipv6=fail

sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/c-over-block.nft --reset
# expect: exit 1, defects=[C, E], ipv4=pass, ipv6=fail

sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/d-fail-open.nft --reset
# expect: exit 1, defects=[D], ipv6=fail

sudo bash harness/run.sh bench/scenarios/02-web-server \
     --config tests/negative/d-scoped-accept.nft --reset
# expect: exit 1, defects=[D], ipv4=pass, ipv6=fail,
#         exactly one failing probe: ssh-from-wan tcp:22 ipv6

sudo bash harness/run.sh bench/scenarios/04-dns-server \
     --config tests/negative/d-v4-only-negative.nft --reset
# expect: exit 1, defects=[D], ipv4=pass, ipv6=fail,
#         exactly two failing probes: ssh-from-wan and echo-from-wan, ipv6

sudo bash harness/run.sh bench/scenarios/03-db-server \
     --config tests/negative/e-nd-blocked.nft --reset
# expect: exit 1, defects=[E], ipv4=pass, 40/41,
#         the only failing probe is ipv6-neighbour-discovery
```

The two D controls are the sharp ones. `d-scoped-accept.nft` differs from the
scenario 02 expert by one line, and `d-v4-only-negative.nft` differs from the
scenario 04 expert by four, so a failure anywhere else would mean the oracle is
over-constrained — a bug in the test, not in the ruleset.

The E control tests the lab rather than the classifier. It is a correct
dual-stack ruleset with discovery refused and every other rule right. If
neighbour entries were not pinned, a dead IPv6 link would fail every allow-probe
and it would report C as well as E. It reports E alone, with every flow probe
still passing, which is the evidence that resolution is no longer on the path.

The A control exists because execution alone cannot distinguish A from D: both
leave the second family open. Only the absence of an IPv6 table separates them,
which is why `score.py` classifies A/B from the text and C/D from the probes.

The expert configuration must still print `PASS` on every probe of the same
oracle. If a negative control passes, or the expert fails, the oracle is wrong —
fix it before writing another scenario.

## Why these six and not more

C and D are the two shapes this project claims are novel and invisible. If the
harness cannot separate those two from a correct configuration, nothing later in
the pipeline is meaningful. Two D controls are needed because D has two
plausible constructions: a scoped drop in a default-drop ruleset, and an
explicit negative match in a default-accept ruleset. A classifier that caught
only one would report half the phenomenon.

A is the failure the literature already knows about, and it is here to keep the
classifier honest about the difference between a missing table and a wrong
default policy. B is detected by the same structural test as A and needs no
separate file. E is the one class that can silently corrupt the others — a
broken IPv6 link looks like an over-block — so it gets a control of its own.
