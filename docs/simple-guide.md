# The Project in Plain Words

A jargon-light explanation of what this repository is, what is in it, and what to
do next. `docs/context.md` is the technical briefing; this is the version you can
hand to someone who has never opened a terminal.

---

## 1. What we are testing

A firewall is a guard at the door of a computer. It checks every network
connection and decides: let it in, or block it.

Computers today have two ways of being addressed: the old **IPv4** and the newer
**IPv6**. A machine that has both is called **dual-stack**, and it needs the
guard to check both doors.

People increasingly ask AI assistants to write firewall rules. This project asks
one question about the result:

> When the AI writes a rule for IPv4, does the same rule actually protect IPv6?

Often it does not, and nothing looks wrong. The file is valid. It loads without
errors. It blocks the bad traffic on IPv4. But on IPv6 the door is still open, or
the owner is locked out.

**The subtle part:** on Linux, a single `nftables` `inet` table is widely assumed
to protect both protocols automatically. It does not. Address matches such as
`ip saddr` apply to **IPv4 only**, even inside an `inet` table. A configuration
can therefore look dual-stack, load cleanly, pass every syntax check, and
silently fail the policy on IPv6.

We answer the question by sending real packets, not by reading the file.

---

## 2. Where the project stands

Two things are proven, and they are the two that matter most.

| Check | Status | Why it matters |
|---|---|---|
| **The lab works** | **Passed 28 Nov** | Three fake computers, both address families, packets actually move |
| **The test can fail** | **Passed 28 Nov** | A hand-written correct firewall scores 100%; the deliberately broken ones are caught with the right defect class |
| **A model has written a firewall** | **Done** | `qwen2.5-coder:7b` ran locally; the first cell already exposed four harness bugs |
| **The benchmark is complete** | **8 scenarios** | All eight service families, each with a 100%-passing hand-written reference |
| **A dataset exists** | **In progress** | A clean C1/C2 pilot across the eight scenarios is running |

The second row is the one people skip. A test suite that has never rejected
anything is a set of assertions that happen to pass — it might be checking
nothing at all. Ours has been made to fail on purpose: six broken
configurations in `tests/negative/`, each caught with exactly its own class
(A, C, D, D, D, E).

---

## 3. What the repository can do today

- Build an isolated lab of three computers with no internet access.
- Load any nftables ruleset into the middle one and report load errors.
- Send real TCP, UDP, ICMP and IPv6-discovery traffic from either side.
- Score the result against a hand-written expectation, separately per family.
- Classify each failure into one of five defect types (A–E), or `S` when the
  ruleset would not load at all.
- Prove the whole thing works by running eight correct rulesets and six broken
  ones.

## 4. What it cannot do yet

- Produce a complete dataset. The first pilot (eight scenarios, two conditions)
  is running; the full matrix is still to come.
- Draw a conclusion. There are no finished numbers yet.

The measuring instrument is finished and has survived its first contact with a
real model. The measurement itself has started.

---

## 5. How to run it, in four commands

Inside Ubuntu (WSL2 on Windows is fine):

```bash
# 1. Check the machine can host the lab
sudo bash scripts/check-env.sh --live

# 2. Run scenario 01 against its expert configuration.
#    Expect: ipv4=pass ipv6=pass parity=pass, 37/37 probes matched, exit 0.
sudo bash harness/run.sh bench/scenarios/01-ssh-bastion --reset

# 3. Run the same scenario against a deliberately broken configuration.
#    Expect: exit 1, defects=['C', 'E'], ipv4=pass, ipv6=fail.
sudo bash harness/run.sh bench/scenarios/01-ssh-bastion \
     --config tests/negative/c-over-block.nft --reset

# 4. See what the model run would do, without doing it
sudo bash scripts/collect.sh --dry-run
```

Step 2 passing and step 3 failing is the whole safety property of the harness.
If step 2 fails, the test is wrong, not the firewall. If step 3 passes, the test
is measuring nothing.

---

## 6. What happens next

The single-cell smoke test is done — it cost one call and found four harness
bugs, which is exactly why it ran before the matrix. The pilot is now the eight
scenarios, two conditions, one repeat:

```bash
sudo bash scripts/collect.sh --conditions C1,C2 --repeats 1 \
     --models local:qwen2.5-coder:7b
```

After that: the remaining four scenarios (to reach twelve), the other two model
slots, then the full three-repeat matrix and the first real numbers. That is
gate **D**, and it is where this stops being a plan and starts being a finding.

---

## 7. Words used in this project

| Word | Plain meaning |
|---|---|
| **Namespace** | A fake computer inside your computer. Has its own network, isolated from everything else. |
| **veth pair** | A virtual cable with two ends. Plug one end into each fake computer. |
| **nftables** | The firewall software built into Linux. |
| **Ruleset** | The firewall's instruction list. What the AI writes. |
| **Policy** | What the owner *wants*: "allow SSH from the office, block everything else". |
| **Probe** | One test packet. "Try to connect to port 22 and see what happens." |
| **Oracle** | The written answer key: what each probe *should* do. |
| **Expert config** | A correct firewall, written by hand, used to prove the answer key is right. |
| **Negative control** | A deliberately broken firewall, used to prove the answer key can fail. |
| **Gate** | A checkpoint. If it fails, stop and fix, because everything after it would be meaningless. |
| **Fail-open** | The door is open when it should be shut. The dangerous one. |
| **Over-block** | The door is shut when it should be open. Annoying, sometimes serious. |
| **Parity** | Behaving the same on IPv4 and IPv6. The property we are measuring. |

---

## 8. Work log — 28 November 2026

This section is a dated record, not a description of the current state. It will
get stale; sections 1–7 will not.

### What happened

I set out to write the harness. While doing so, the repository moved ahead by
fourteen commits that had already built it — and further along than my version:
run on a real WSL2 machine, three bugs found and fixed, two extra scenarios
added, plus a model runner and an analysis script.

When I pushed, GitHub rejected it. I did not merge two competing harnesses. I
discarded mine and kept the one that had actually been executed and debugged. A
harness that has never run is a hypothesis; the one on GitHub has been run and
fixed. Keeping both would have meant maintaining two versions of the same thing.

### What I actually contributed

Documentation drift repair. `docs/context.md` and `docs/pipeline.md` still
claimed the lab was not installed and the harness had never executed. Both were
false by then. Corrected:

| Old claim | What is actually true |
|---|---|
| "harness written, never executed" | Implemented, executed, three bugs found and fixed |
| "WSL2 not installed — hard blocker" | Installed; the lab pings across both address families |
| "negative controls expected to fail" | Run; they fail with the correct defect classes |
| "model runner: 0 lines written" | Written; not yet run against a model |
| "one scenario" | Four scenarios: SSH, web, database, DNS |
| "PASS 11/11" | The real figure is 37 executed checks for scenario 01 |

Two files I wrote are not in the repository: a standalone scenario validator and
a set of logic unit tests. They were dropped rather than duplicate the checks
that already live in `harness/score.py`. They can be added back if they turn out
to be useful.

### The honest lesson

The harness I wrote looked correct and had never run. The one that replaced it
looked similar and had run. That difference — one execution — was worth more
than the code itself. It is the same reason the project has an expert gate and
negative controls: correctness you have not tried to break is a guess.
