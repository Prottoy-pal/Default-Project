# Sprint 1 — Two Weeks to a Working Pilot

**Dates:** Mon 23 November → Sun 6 December 2026
**Effort:** ~2–3 hours per day (~35 hours total)
**Goal:** A reproducible lab, 6 validated scenarios, and a first real dataset.

> **Definition of done:** someone else can clone this repository, run `bash scripts/check-env.sh`, then `bash harness/run.sh`, and reproduce your pilot numbers — without asking you a single question.

---

## The one rule

**The expert configuration must pass 100% of its tests before you ever prompt a model.**

If `expert.nft` fails, your tests are wrong — not the model. Fix the tests. No exceptions.

---

## Three decision gates

| Gate | When | Pass condition | If it fails |
|---|---|---|---|
| **G1 — Lab works** | End of Day 2 (Tue 24) | `nft` loads a ruleset inside a namespace; `ping` succeeds over IPv4 **and** IPv6 across the veth pair | **Stop everything and fix it.** This is the #1 project killer. Nothing downstream is meaningful without it. |
| **G2 — Models reachable** | Day 8 (Mon 30) | One local Ollama model answers + one free-tier API key works | Go local-only. A single model still produces a valid pilot. |
| **G3 — Pilot data exists** | Day 11 (Thu 3) | ≥6 scenarios × 3 models × C1 × 3 repeats stored as JSON | Cut to 4 scenarios. Keep 3 models and 3 repeats. |

---

## Week 1 — Make the lab real

| Day | Date | Task | Output | Time |
|---|---|---|---|---|
| **1** | Mon 23 | Install WSL2 + Ubuntu 24.04 (`wsl --install -d Ubuntu`, then reboot). Verify `nft --version`, `ip -6 addr`. | Screenshot + `docs/lab-notes.md` started | 90 min |
| **2** | Tue 24 | Build the lab: three namespaces (`fw`, `cli_admin`, `cli_wan`), two veth pairs, addresses straight from `bench/topology.yaml`. Trivial nft ruleset. Ping both families. | `bash scripts/check-env.sh --live` green ✅ **G1** | 3 h |
| **3** | Wed 25 | Port the same build into `harness/lab.py` (build, teardown, deterministic reset). Write `harness/probe.py` v0: TCP connect, UDP, ICMP, ND; emit JSON. | `lab.py`, `probe.py` | 3 h |
| **4** | Thu 26 | **Scenario 01 — SSH bastion.** Write `policy.yaml`, `expected.yaml`, `expert.nft`. Iterate until expert passes 100%. | `bench/scenarios/01-ssh-bastion/` | 3 h |
| **5** | Fri 27 | Scenarios 02 (web server) and 03 (DB server). **Freeze the YAML schema** — after today the format stops changing. | 2 scenarios + schema note | 3 h |
| **6** | Sat 28 | **Negative controls.** Hand-write two deliberately broken configs: defect **C** (`inet` + `policy drop` + `ip saddr`) and defect **D** (`inet` + `policy accept` + `ip saddr drop`). Your harness must flag both. | `tests/negative/` + confirmation both are caught | 3 h |
| **7** | Sun 29 | Week 1 review. Finish `docs/lab-notes.md`. Tag `v0.1-lab`. | Git tag | 90 min |

**Week 1 success looks like:** you can break a firewall on purpose, and your harness tells you exactly which probe failed and on which family.

---

## Week 2 — Make it produce data

| Day | Date | Task | Output | Time |
|---|---|---|---|---|
| **8** | Mon 30 | Install Ollama, pull one 7–8B model. Test one free API. Record exact tags. Write the three prompt templates (C1/C2/C3). | `generate/prompts/` ✅ **G2** | 2 h |
| **9** | Tue 1 | `generate/run_models.py`: call model → extract fenced code block → apply → probe → score → JSON row. Run one model on 3 scenarios. | First real results | 3 h |
| **10** | Wed 2 | Expand to 6 scenarios. Run **C1** × 3 models × 3 repeats. | ~54 configurations | 2 h + unattended |
| **11** | Thu 3 | Run **C2** (explicit dual-stack) and **C3** (RAG over nftables wiki + `man nft`). Log retrieved passages for every C3 call. | C2/C3 results ✅ **G3** | 3 h + unattended |
| **12** | Fri 4 | Analysis: parity rate, Wilson CIs, defect coding by class A–E, static-heuristic vs execution agreement. | `results/pilot-summary.csv` + first table | 3 h |
| **13** | Sat 5 | Two figures: (1) IPv4 vs IPv6 pass rate, (2) defect-class distribution. Draft the pilot section of Stage 2. | `docs/pilot-report.md` | 3 h |
| **14** | Sun 6 | Release: tag `v0.2-pilot`, push, create Zenodo DOI, update README status table. | Public release | 2 h |

---

## Cut list — apply in this order if you fall behind

| Priority | Cut | Cost of cutting |
|---|---|---|
| 1st | C4 repair loop | Loses one intervention; C1–C3 still answer RQ3 partly |
| 2nd | Third model | Weakens the model-comparison claim, not the main finding |
| 3rd | C3 RAG | Loses RQ3's second half; RQ1/RQ2 intact |
| 4th | Reduce to 4 scenarios | Shrinks CIs; still a valid pilot |
| **Never** | Expert gate | Without it, no result is trustworthy |
| **Never** | IPv6-disabled control | Without it, you cannot separate defect from artefact |
| **Never** | 3 repeats | Without it, no variance estimate |

---

## Daily checklist (copy into your notes each day)

```
[ ] Did the expert config still pass 100%?
[ ] Did I record the model tag / version?
[ ] Did I commit with a message that explains *why*, not just *what*?
[ ] Did I write down one thing that surprised me?
```

---

## What you should be able to say on 6 December

> "I have an isolated dual-stack lab, six policy scenarios with hand-verified ground truth, and a first dataset of ~150 LLM-generated nftables configurations, scored by execution on both address families. I know which defect classes appear, and whether my harness detects them reliably."

If you cannot say that, the sprint failed — and you will know on Day 7, not on Day 13. That is the point of the gates.
