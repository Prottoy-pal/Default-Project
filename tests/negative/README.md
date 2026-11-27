# Negative controls

Two configurations that are **deliberately wrong**, written so that the oracle
has something to fail against.

An oracle you have never seen fail is not an oracle. It is a set of assertions
that happen to pass.

| File | Defect | What it pretends to be | What it actually does |
|---|---|---|---|
| `c-over-block.nft` | **C** | Strict, dual-stack | Locks the administrator out over IPv6 |
| `d-fail-open.nft` | **D** | Hardened | Leaves SSH and every other port open over IPv6 |

Run both against scenario 01:

```bash
sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/c-over-block.nft --reset
# expect: exit 1, defects=[C, E], ipv6=fail, ipv4=pass

sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/d-fail-open.nft --reset
# expect: exit 1, defects=[D], ipv6=fail
```

The expert configuration must still print `PASS 11/11` on the same oracle. If
the negative controls pass, or the expert fails, the oracle is wrong — fix it
before writing another scenario.

## Why these two and not more

C and D are the two shapes this project claims are novel and invisible. If the
harness cannot separate those two from a correct configuration, nothing later in
the pipeline is meaningful. Class A, B and E are detected by the same execution
data and are exercised naturally by failing model output.
