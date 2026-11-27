# Research Plan

**Half a Firewall: Execution-Based Evaluation of IPv6 Policy Coverage in LLM-Generated Linux Firewall Configurations**

Last updated: 23 November 2026

---

## 1. Problem

Large language models are increasingly used to turn a sentence into a firewall configuration. The output usually looks right: valid syntax, sensible rule order, a plausible `policy drop`. Evaluation practice — and the benchmarks that support it — asks whether the artifact **matches the stated intent**.

The stated intent is almost always expressed in one address family. A policy like *"allow SSH from the admin subnet"* is written once and silently assumed to hold for both IPv4 and IPv6.

On Linux it does not hold automatically:

- `iptables` and `ip6tables` are **separate tables**. Rules in one do not affect the other.
- `nftables` offers an `inet` family that covers both — but **match expressions remain family-specific**. `ip saddr 10.0.0.0/16` matches IPv4 only; the IPv6 equivalent requires `ip6 saddr`.
- In a chain with `policy drop`, a family-scoped allow rule silently **locks out** the other family (over-block).
- In a chain with `policy accept`, a family-scoped deny rule silently **lets everything through** on the other family (fail-open).

A configuration can therefore be syntactically perfect, pass a schema validator, pass a similarity metric against a reference answer, and still not implement the policy.

**This defect is invisible to every functional test that does not probe both families.**

---

## 2. Gap

Two literatures exist and do not meet.

**(i) LLM network configuration.** NetConfEval (Wang et al., CoNEXT 2024) benchmarks translation of requirements into formal specifications. NetLLMBench (NFV-SDN 2024) evaluates configuration tasks in emulated networks. NetConfArena (2026) runs closed-loop agents against executable test cases. Cornetto (2026) benchmarks configuration *repair*. Colombo & Martinello (SBRC 2026) add a four-stage verification pipeline ending in Mininet packet tests and show a 20-point gap between syntactic and operational success.

**All of these validate against a stated intent. None of them asks whether the intent holds on the second address family.**

**(ii) IPv6 exposure.** Czyz et al. (NDSS 2016) showed real networks enforce weaker policy on IPv6. "Where Have All the Firewalls Gone?" (2025) measured 93.8 million reachable IPv6 addresses and concluded NAT had been the de facto residential firewall.

**(iii) The intersection is empty.** As of November 2026:

| Query | Result |
|---|---|
| arXiv `abs:"dual-stack" AND abs:"large language model"` | **0** |
| arXiv `abs:"rule anomal" OR abs:"rule shadowing"` | **0** |
| arXiv `abs:"iptables"` (entire archive) | 13 |
| arXiv `abs:"firewall configuration"` | 9 (none involving LLMs) |
| HuggingFace `iptables` / `nftables` / `firewall rules` | **0 / 0 / 0 datasets** |

**Claim to be defended:** *we are not the first to have LLMs write firewall rules; we are the first to measure their dual-stack behavioural parity.*

**The sharpest formulation:** Colombo & Martinello's pipeline would score a configuration with an empty IPv6 table as **correct**, because it validates against an intent that is IPv4-only. We ask the question their verification structurally cannot.

---

## 3. Research questions

### RQ1 — Prevalence
Under a plain prompt with an explicitly dual-stack policy, what proportion of generated configurations fail to enforce the policy on at least one family, and how does the IPv4 failure rate compare with the IPv6 failure rate?

### RQ2 — Mechanism
Which construction patterns predict failure? Can any static heuristic — rule counting, presence of `inet`, presence of an `ip6` table — predict execution outcomes?

### RQ3 — Intervention
Do explicit dual-stack instruction, documentation-grounded RAG, or execution-feedback repair reduce failure — and which defect classes respond to which intervention?

### Hypotheses (pre-registered)

- **H1** — IPv6 enforcement is weaker than IPv4 under plain prompting.
- **H2** — Defect class depends on dialect: family omission → fail-open; family-scoped match inside `inet` → over-block under `policy drop`, fail-open under `policy accept`.
- **H3** — RAG reduces family-omission defects and does not reduce family-scoped-match defects, because documentation discusses the former and not the latter.

---

## 4. Design

### 4.1 Two-tier oracle

Every scenario carries two layers of expectation:

| Tier | Contents | Purpose |
|---|---|---|
| **Specified** | Flows the user explicitly asked for | Functional correctness |
| **Silent** | Flows implied by a hardening baseline that the user never mentioned | Security correctness |

A configuration can pass Tier 1 and fail Tier 2. **The gap between the two verdicts is the finding.**

### 4.2 Task suite

Eventually 32 scenarios: **8 families × 4 variants**.

| Axis | Levels |
|---|---|
| Family | SSH bastion · web server · DB server · DNS resolver · container host · forwarding gateway · monitoring host · mixed bastion+web |
| Variant | (i) any source, default drop · (ii) scoped source, default drop · (iii) any source, default accept · (iv) scoped source, default accept |

Variant (ii) triggers defect **C**. Variant (iv) triggers defect **D**. This is what makes attribution possible — a failure can be traced to a design feature, not to a hand-written scenario's quirks.

**Sprint 1 target: 6 scenarios. Course minimum: 12. Full benchmark: 32.**

### 4.3 Conditions

| Code | Condition | Model receives |
|---|---|---|
| **C1** | Plain | The policy only |
| **C2** | Explicit dual-stack | Policy + "the ruleset must enforce this policy for both IPv4 and IPv6 traffic" |
| **C3** | RAG | Policy + retrieved passages from nftables wiki, `man nft`, CIS benchmarks |
| **C4** | Repair (optional) | C1, then sees which probes failed and retries, up to 2 rounds |

### 4.4 Models

Three models minimum: at least one local (Ollama), at least one free-tier API. Record **exact tag, quantisation, temperature, top_p**. Three repeats per cell.

### 4.5 Controls (non-negotiable)

1. **Expert gate** — a hand-written `expert.nft` must pass 100% of `expected.yaml` before any model is prompted. If it fails, the tests are wrong.
2. **IPv6-disabled control** — repeat a subsample with `net.ipv6.conf.all.disable_ipv6=1`. A missing v6 rule is not a failure where v6 does not exist.
3. **Deterministic reset** — fresh namespace or VM snapshot per run. No state carries over.

---

## 5. Metrics

| Metric | Definition | Statistic |
|---|---|---|
| Syntax validity | Applies without error | proportion + Wilson CI |
| IPv4 correctness | All IPv4 probes match expectation | proportion + Wilson CI |
| IPv6 correctness | All IPv6 probes match expectation | proportion + Wilson CI |
| **Parity** | Both families correct | proportion + Wilson CI |
| **Silent-exposure rate** | Tier 1 pass ∧ Tier 2 fail | proportion + Wilson CI |
| Fail-open count | Traffic that should be blocked but passes | count |
| Over-block count | Traffic that should be allowed but is blocked | count |
| **Exposure delta** | reachable services on v6 − on v4 | median + IQR, Wilcoxon |
| Static-check agreement | Heuristic verdict vs execution verdict | Cohen's κ |
| RAG effect | C3 vs C1, paired by scenario | McNemar |
| Model effect | Across models, scenario as random effect | mixed-effects logistic |

**Decision rule:** a configuration that fails to load counts as failure on **both** families.

**Power:** with 32 scenarios × 3 models × 3 conditions × 3 repeats ≈ 864 cells, a proportion near 0.5 has a 95% Wilson interval half-width of ≈ ±3.3%. State this; do not over-claim small differences between models.

---

## 6. Threats to validity

| Threat | Mitigation |
|---|---|
| Our tests are wrong, not the model | Expert gate at 100%; second coder on 20% of scenarios |
| Missing IPv6 rule is not always a defect (`inet`, UFW) | Execution-based measurement, never rule counting; IPv6-disabled control |
| Prompt wording drives results | Treat wording as a variable (C1 vs C2), do not tune it between runs |
| Model drift over time | Record exact version/tag; publish raw outputs |
| Benchmarked against models that memorised the benchmark | Scenarios are original; no public corpus contains them |
| Only one observation per cell | 3 repeats; report variance |
| `iptables` on Ubuntu 24.04 is `iptables-nft` | Core study is nftables-native; state the shared backend explicitly |

---

## 7. Timeline (course)

| Week | Work | Rubric stage |
|---|---|---|
| 1 (23–29 Nov) | Lab, scenarios 1–6, harness green | Stage 1 |
| 2 (30 Nov–6 Dec) | Model runs, pilot analysis, Stage 2 draft | Stage 2 |
| 3 | Freeze benchmark at 32; validate expert configs | Stage 2 |
| 4 | C1 + C2 full runs | Stage 3 |
| 5 | C3 (RAG) runs; retrieval logs | Stage 3 |
| 6 | Analysis, taxonomy coding, figures, draft | Stage 3 |
| 7 | Final report, artifact, viva prep | Stage 4 |

Detailed two-week sprint: [sprint-01.md](sprint-01.md).

---

## 8. Deliverables

1. **Benchmark** — scenarios with declared expectations, expert configs, probe definitions (MIT, Zenodo DOI).
2. **Harness** — apply / probe / score, reproducible on any Linux box.
3. **Raw dataset** — every generated configuration, verdict, and model version.
4. **Defect taxonomy** — A–E with real examples.
5. **Paper** — course submission, then workshop.

---

## 9. Publication route

| Level | Target |
|---|---|
| Course | CSE 4531 Stage 4 report + viva |
| Workshop | CAMLIS · ACM ANRW · USENIX WOOT · NDSS MADWeb |
| Full | ACM IMC · USENIX Security · ACM CoNEXT |
| Regional | NSysS (Dhaka) · ICCIT |

---

## 10. What is *not* in scope

- Windows Defender Firewall, pfSense, Cisco ACLs, cloud security groups.
- Writing a firewall or an IDS.
- Fine-tuning models (that is Zhang et al.'s contribution, not ours).
- Attacking any system we do not own.
- IPv6 extension-header evasion or tunnelling.
