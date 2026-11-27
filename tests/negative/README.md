# Negative controls

Three configurations that are **deliberately wrong**, written so that the
oracle has something to fail against.

An oracle you have never seen fail is not an oracle. It is a set of assertions
that happen to pass.

| File | Defect | What it pretends to be | What it actually does |
|---|---|---|---|
| `c-over-block.nft` | **C** | Strict, dual-stack | Locks the administrator out over IPv6 |
| `d-fail-open.nft` | **D** | Hardened | Leaves SSH and every other port open over IPv6 |
| `d-scoped-accept.nft` | **D** | Correct default-accept ruleset | Drops SSH from the untrusted zone over IPv4 only |

Run them against their scenarios:

```bash
sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/c-over-block.nft --reset
# expect: exit 1, defects=[C, E], ipv6=fail, ipv4=pass

sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/d-fail-open.nft --reset
# expect: exit 1, defects=[D], ipv6=fail

sudo bash harness/run.sh bench/scenarios/02-web-server \
     --config tests/negative/d-scoped-accept.nft --reset
# expect: exit 1, defects=[D], ipv4=pass, ipv6=fail,
#         exactly one failing probe: ssh-from-wan tcp:22 ipv6
```

The third file is the sharper control. It differs from the scenario 02 expert
by one line, so a failure anywhere else would mean the oracle is
over-constrained — a bug in the test, not in the ruleset.

The expert configuration must still print `PASS` on every probe of the same
oracle. If a negative control passes, or the expert fails, the oracle is wrong —
fix it before writing another scenario.

## Why these three and not more

C and D are the two shapes this project claims are novel and invisible. If the
harness cannot separate those two from a correct configuration, nothing later in
the pipeline is meaningful. Class A, B and E are detected by the same execution
data and are exercised naturally by failing model output.
