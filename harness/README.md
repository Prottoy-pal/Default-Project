# harness/

Everything that turns a configuration file into a verdict. Four jobs, four
modules, one command.

```
common.py         topology loading, endpoint resolution, subprocess
lab.py            build, reset, tear down the three namespaces
apply.py          load a candidate ruleset into the device under test
probe.py          turn one probe description into real packets
score.py          compare observed behaviour against expected.yaml, emit one JSON row
run.sh            the only entry point anyone else needs to know
_sink.py          the services the lab probes against (started by lab.py)
_probe_helper.py  executes one probe inside one namespace, in a child process
```

**Status:** executed 28 November 2026, Ubuntu 26.04.1 / nftables 1.1.6. Gate B
passed: scenario 01 expert 37/37, scenario 02 expert 21/21, and the negative
controls exit 1 with the expected classes. The three bugs found by running it
(arguments to `ip netns`, missing peer routes, exit code 1 for harness failure)
are fixed; that is why the status is a date and not a promise.

---

## The command

```bash
sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config bench/scenarios/01-ssh-bastion/expert.nft \
     --out results/expert-01.json --reset
```

| Flag | Meaning |
|---|---|
| `--config PATH` | A ruleset file. Defaults to the scenario's own `expert.nft`. |
| `--out PATH` | The JSON row to write. Default `results/<run_id>.json`. |
| `--condition C1\|C2\|C3\|C4` | Recorded in the row; does not change behaviour. |
| `--repeat N`, `--model M` | Recorded in the row and in the `run_id`. |
| `--reset` | Rebuild the lab before applying. Required for any recorded run. |
| `--keep` | Leave the lab running after the run, for inspection. |

`generate/run_models.py` is the normal caller: it always passes `--reset`,
because a row that inherits state from the previous one is not a measurement.

Exit codes: `0` every probe matched expectation · `1` at least one probe
disagreed · `2` the harness itself failed (lab error, unparseable oracle).
`2` must never be recorded as a model failure.

---

## Invariants

These are not defaults. Breaking one invalidates the row.

1. **Reset before every apply.** Tear the lab down and rebuild it, or restore
   from the snapshot. A ruleset that inherits a previous chain is not the
   ruleset that was generated.
2. **`flush ruleset` is not injected on the model's behalf.** If a generated
   configuration appends rules to whatever was already loaded, that is part of
   what is being measured.
3. **A load failure is not a behavioural class.** A ruleset that will not
   apply protects nothing, so it is recorded as `defects: ["S"]` with
   `load_failure: true` and `verdicts: not-loaded` on both families. Folding it
   into A–E would report "does not compile" as "fails on IPv6". The stderr is
   kept verbatim.
4. **No packet leaves the machine.** All three namespaces are local; there is
   no bridge and no default route out.
5. **A timeout is a drop, never an error.** Probe results are `allow`,
   `drop`, or `error`. `error` fails the run and is not scored.
6. **Every row records the model version and the prompt hash.** A result that
   cannot be tied to an exact artifact is not a result.

---

## How a probe becomes a verdict

| Probe type | Sends | Reads as `allow` when |
|---|---|---|
| `tcp` | SYN to `dport`, bound to the source address | handshake completes |
| `udp` | datagram to `dport` | any reply, or an ICMP port-unreachable, arrives within the timeout |
| `icmp-echo` | echo request | echo reply arrives |
| `icmp6-nd` | ping after removing the peer's pinned neighbour entry | the entry comes back `REACHABLE` |

`lab.py` pins a permanent neighbour entry for every peer on every link. That
is what stops a ruleset which drops ICMPv6 from taking the second family down
for every probe at once — a dead link fails allow-probes and passes drop-probes
vacuously, so one defect would be scored as two. The `icmp6-nd` probe removes
its own entry before pinging and restores it afterwards, so whether the policy
answers discovery is still measured, and measured on its own.

A probe is scored `fail` when `observed != expected` for that family. The row
keeps `expected` and `observed` side by side, so a wrong oracle is visible in
the data rather than hidden in an aggregate.

Defect classification reads the failure pattern, not the file text — except for
A and B, which execution cannot separate from D:

| Pattern | Class |
|---|---|
| no IPv6 table at all (`table ip` only) | **A** |
| split `ip`/`ip6` tables whose v6 chain filters nothing | **B** |
| v6 allow-probes fail, v6 drop-probes pass | **C** — over-block |
| v6 allow-probes pass, v6 drop-probes fail | **D** — fail-open |
| the `icmp6-nd` probe gets no advertisement | **E** — ICMPv6 mishandled |
| the ruleset did not load | **S** — not a class; excluded from A–E |

The static heuristics (`has_inet`, `has_ip6_table`, `rule_count`,
`family_scoped_matches`) are recorded **alongside** the execution verdict and
never instead of it. Their agreement rate is a result (RQ2), not an input.

---

## Output

One JSON object per configuration, one file per run. The schema is frozen once
the first dataset is collected; until then it is:

```json
{
  "run_id": "2026-12-02T11-04-07Z__01-ssh-bastion__C1__model__r1",
  "scenario": "01-ssh-bastion",
  "condition": "C1",
  "repeat": 1,
  "model": { "provider": "", "name": "", "tag": "", "temperature": 0.0, "top_p": 1.0 },
  "generation": { "prompt_sha256": "", "raw_output": "", "extracted_ruleset": "" },
  "apply": { "loaded": true, "stderr": "", "duration_ms": 42 },
  "probes": [
    { "id": "ssh-from-admin", "family": "ipv6", "proto": "tcp",
      "expected": "allow", "observed": "drop", "verdict": "fail",
      "resolution": "ok", "latency_ms": 1201 }
  ],
  "verdicts": { "ipv4": "pass", "ipv6": "fail", "parity": "fail",
                "specified": "pass", "silent": "fail" },
  "defects": ["C"],
  "heuristics": { "has_inet": true, "has_ip6_table": false,
                  "rule_count": 7, "family_scoped_matches": 2 }
}
```

`raw_output` is stored verbatim, including the model's prose. Post-processing
that loses the original answer is not reproducible.

---

## Before the first real run

```bash
bash scripts/check-env.sh --live     # lab is possible at all
bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config bench/scenarios/01-ssh-bastion/expert.nft
```

The second command must print `PASS 11/11`. If it does not, stop. Every number
produced after that point would be measuring the harness.
