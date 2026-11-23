# Project Context

**Everything about this project in one file** — the problem, the gap, the design,
the current state, and what happens next. Written for a reader who has five
minutes and needs to judge whether the work is sound.

Last updated: 24 November 2026

---

## 1. What this is

A research project for **CSE 4531 Computer Security, United International
University (Fall 2026)** — 30 marks, four rubric stages, one student, **$0
budget**, one laptop.

It measures whether Linux firewall configurations written by a large language
model enforce the same security policy over **IPv4** and **IPv6**, and it
answers that question by **executing** the configuration and sending real
packets, not by reading the text.

**Title:** *Half a Firewall: Execution-Based Evaluation of IPv6 Policy Coverage
in LLM-Generated Linux Firewall Configurations*

**Rubric mapping:** T1 (LLM and agentic security) primary · T11 (vulnerability
discovery) secondary · T19 (security policy) as the framing.

---

## 2. The problem, in one page

A firewall decides, per packet: allow or block. A machine that speaks both
address families at once is **dual-stack**, and a dual-stack machine needs the
same decision enforced twice.

The failure this project studies is not a crash. It is a configuration that
loads cleanly, reads correctly, passes every syntax and schema check — and
enforces the policy on one family only.

On Linux, three facts make that possible:

| Fact | Consequence |
|---|---|
| `iptables` and `ip6tables` are **separate tables** | Rules in one never affect the other. Omission is invisible. |
| `nftables` has an `inet` family covering both protocols | Commonly *assumed* to mean "dual-stack by default". It does not. |
| Inside `inet`, **match expressions stay family-scoped** | `ip saddr 10.20.0.0/24` matches IPv4 only. IPv6 needs `ip6 saddr`. |

The last fact is the whole study. It produces two opposite failures, and both
look correct on the page:

| Chain policy | Rule written | IPv4 behaviour | IPv6 behaviour | Name |
|---|---|---|---|---|
| `policy drop` | `ip saddr … accept` | allowed as intended | **silently blocked** | over-block |
| `policy accept` | `ip saddr … drop` | dropped as intended | **silently allowed** | fail-open |

The first locks the administrator out of the host over IPv6. The second leaves
the host wide open over IPv6 while the ruleset appears to block the attacker.
Neither is visible to any test that probes only one address family.

---

## 3. The gap

Two literatures exist and do not meet.

**(i) LLM network configuration.** Benchmarks now verify generated network
configurations by execution: NetConfEval (CoNEXT 2024), NetLLMBench (NFV-SDN
2024), NetArena, NetConfArena, Cornetto, and — closest to this work — Colombo &
Martinello (SBRC 2026), whose four-stage pipeline ends in Mininet packet tests
and reports a 20-point gap between syntactic and operational success.

**All of them validate against a stated intent. None asks whether that intent
holds on the second address family.**

**(ii) IPv6 exposure.** Czyz et al. (NDSS 2016) showed real networks enforce
weaker policy on IPv6 than on IPv4, with all twelve contacted operators
confirming the extra openness was unintentional. "Where Have All the Firewalls
Gone?" (2025) found 93.8 million reachable IPv6 addresses and concluded that NAT
had been the de facto residential firewall.

**(iii) The intersection is empty.** Searches run in November 2026:

| Query | Result |
|---|---|
| arXiv `abs:"dual-stack" AND abs:"large language model"` | **0** |
| arXiv `abs:"rule anomal" OR abs:"rule shadowing"` | **0** |
| arXiv `abs:"iptables"` (entire archive) | 13 |
| arXiv `abs:"firewall configuration"` | 9, none involving LLMs |
| arXiv `abs:"IPv6" AND abs:"large language model"` | 3, none on policy enforcement |
| HuggingFace `iptables` / `nftables` / `firewall rules` | **0 / 0 / 0 datasets** |
| Zenodo iptables collection | exists, explicitly **IPv4-only** |

**Claim defended:** we are not the first to have LLMs write firewall rules; we
are the first to measure their **dual-stack behavioural parity**.

**The sharpest formulation — use verbatim:**

> Colombo & Martinello's verification pipeline [SBRC 2026] would score a
> configuration with an empty IPv6 table as *correct*, because it validates
> against an intent that is IPv4-only. We ask the question their verification
> structurally cannot.

---

## 4. Research questions

| ID | Question |
|---|---|
| **RQ1 — Prevalence** | Under a plain prompt with an explicitly dual-stack policy, what proportion of generated configurations fail to enforce the policy on at least one family, and how does the IPv4 failure rate compare with the IPv6 failure rate? |
| **RQ2 — Mechanism** | Which construction patterns predict failure (family omission, split tables, family-scoped matches, default-policy choice, ICMPv6 handling)? Can any static heuristic — rule counting, presence of `inet`, presence of an `ip6` table — predict execution outcomes? |
| **RQ3 — Intervention** | Do explicit dual-stack instruction, documentation-grounded RAG, or execution-feedback repair reduce failure — and **which defect classes respond to which intervention**? |

### Hypotheses, registered before data collection

| ID | Hypothesis | Falsified if |
|---|---|---|
| **H1** | IPv6 enforcement is weaker than IPv4 under plain prompting. | IPv6 and IPv4 pass rates are statistically indistinguishable. |
| **H2** | Failure mechanism depends on dialect: family omission → fail-open; family-scoped match inside `inet` → over-block under `policy drop`, fail-open under `policy accept`. | One mechanism dominates regardless of variant. |
| **H3** | RAG fixes family omission and does **not** fix family-scoped matches, because documentation discusses the former and not the latter. | RAG reduces both classes equally, or neither. |

H3 is the interesting one. It predicts a *selective* intervention — the kind of
result that is publishable because it is non-obvious and, if wrong, informative.

---

## 5. Design

### 5.1 Two-tier oracle

Every scenario carries two layers of expectation:

| Tier | Contents | Question |
|---|---|---|
| **Specified** | Flows the prompt explicitly asks about | Did the model implement what it was told? |
| **Silent** | Flows implied by a competent implementation, never stated (IPv6 neighbour discovery, closed unnamed ports, loopback intact) | Did it implement what it should have known? |

A configuration can pass every specified probe and fail a silent one. **The gap
between the two verdicts is the finding:** the policy reads as satisfied while
the host is not protected.

### 5.2 Task suite — 8 families × 4 variants

| Axis | Levels |
|---|---|
| **Family** | SSH bastion · web server · DB server · DNS resolver · container host · forwarding gateway · monitoring host · mixed bastion+web |
| **Variant** | any source / default drop · **scoped source / default drop** · any source / default accept · **scoped source / default accept** |

The two bolded variants are the ones that trigger the novel defects **C** and
**D**. The 2 × 2 is what makes attribution possible: a failure can be traced to
a design feature of the scenario rather than to a hand-written scenario's quirks.

**Targets:** 6 scenarios for Sprint 1 · 12 is the course minimum · **32 is the
full benchmark**.

### 5.3 Conditions

| Code | Model receives | Isolates |
|---|---|---|
| **C1** | The policy only | Baseline knowledge |
| **C2** | C1 + "this server has a public IPv4 and a public IPv6 address" | Whether the model knew, or needed telling |
| **C3** | C1 + retrieved nftables wiki / `man nft` / RFC 9099 passages | Whether documentation closes the gap |
| **C4** *(optional)* | C1, then the failing probes, then up to 2 retries | Whether feedback closes the gap |

C1 vs C2 is the load-bearing comparison. If C1 ≈ C2, plain prompting is already
family-aware and the finding is narrow but real. If C1 < C2, the failure is a
prompting artefact — arguably the more actionable result, because it names the
one sentence an operator should add.

### 5.4 Models

Three minimum: one local (Ollama, 7–8B), one hosted frontier model on a free
tier, one contrast. Record exact tag, quantisation, temperature (0.0), top_p,
provider and date. **Three repeats per cell.**

### 5.5 Three non-negotiable controls

1. **Expert gate** — a hand-written `expert.nft` must pass 100% of its oracle
   before any model is prompted. If it fails, the *test* is wrong, not the model.
2. **IPv6-disabled control** — a subsample re-run with
   `net.ipv6.conf.all.disable_ipv6=1`. A missing IPv6 rule is not a defect where
   IPv6 does not exist; this separates a real defect from an artefact.
3. **Deterministic reset** — fresh namespace per run, always. No state carries
   between configurations, and `flush ruleset` is never injected on the model's
   behalf.

---

## 6. Defect taxonomy

| # | Construction | Effect on the other family | Direction | Novel |
|---|---|---|---|---|
| **A** | `table ip` only; no `ip6` table, no `inet` | IPv6 traverses no chain | fail-open | no |
| **B** | `table ip` + `table ip6`, v6 chain empty or `policy accept` | Same, but looks deliberate | fail-open | no |
| **C** | `inet` + `policy drop` + `ip saddr … accept` | IPv6 admin/services unreachable | over-block | **yes** |
| **D** | `inet` + `policy accept` + `ip saddr … drop` | IPv6 attack traffic never dropped | fail-open | **yes** |
| **E** | `icmp type` where `icmpv6 type` is needed; blanket `icmpv6 drop` | Neighbour discovery dies → IPv6 non-functional | over-block | partly |

Classes **C and D** are the contribution. They survive every rule-counting
check, every schema validator, and every similarity metric computed against a
reference answer — because the configuration is textually a superset of a
correct answer written for IPv4.

---

## 7. Metrics

| Metric | Definition | Statistic |
|---|---|---|
| Syntax validity | Applies without error | proportion + Wilson CI |
| IPv4 / IPv6 correctness | All probes in that family match expectation | proportion + Wilson CI |
| **Parity** | Both families correct | proportion + Wilson CI |
| **Silent-exposure rate** | specified pass ∧ silent fail | proportion + Wilson CI |
| Fail-open count | Should be blocked, passes | count |
| Over-block count | Should be allowed, is blocked | count |
| **Exposure delta** | reachable services on v6 − on v4, from the untrusted zone | median + IQR, Wilcoxon |
| Static-check agreement | Heuristic verdict vs execution verdict | Cohen's κ |
| RAG effect | C3 vs C1, paired by scenario | McNemar |
| Model effect | Across models, scenario as random effect | mixed-effects logistic |

**Decision rules.** A configuration that fails to load counts as failure on
**both** families. A timeout is a drop, never an error.

**Power.** 32 scenarios × 3 models × 3 conditions × 3 repeats ≈ 864 cells; a
proportion near 0.5 has a 95% Wilson half-width of ≈ ±3.3%. Small differences
between models are therefore not claims we can make, and the report will say so.

---

## 8. Threats to validity

| Threat | Mitigation |
|---|---|
| Our tests are wrong, not the model | Expert gate at 100%; a second coder on 20% of scenarios |
| A missing IPv6 rule is not always a defect | Execution-based measurement, never rule counting; IPv6-disabled control |
| Prompt wording drives results | Wording is a variable (C1 vs C2); never tuned between runs |
| Model drift over time | Exact version/tag recorded; raw outputs published verbatim |
| Scenarios leaked into training data | Scenarios are original; no public corpus contains them |
| One observation per cell | 3 repeats, variance reported |
| `iptables` on Ubuntu 24.04 is `iptables-nft`; UFW also uses the nftables backend | Core study is nftables-native; shared backend stated explicitly |
| Some flows cannot be probed cleanly (stateful return traffic, PMTUD) | Declared in `unprobed` per scenario, never silently omitted |

---

## 9. Repository map

```
README.md                     landing page: RQs, taxonomy, pipeline, quick start
LICENSE                       MIT
CITATION.cff                  citation metadata for Zenodo / reviewers
.gitattributes                forces LF so shell scripts survive Windows → WSL
.gitignore                    ignores raw results, secrets, caches
docs/
  context.md                  ← this file
  research-plan.md            full design: gap, RQs, metrics, threats, timeline
  sprint-01.md                14-day plan, gates G1–G3, cut list
  related-work.md             literature table with artifact availability
  ethics.md                   host-only rule, snapshot rule, data handling
bench/
  topology.yaml               3 namespaces, 2 veth pairs, all addresses
  scenarios/README.md         scenario schema + six authoring rules
  scenarios/_template/        policy.yaml · expected.yaml · expert.nft  (skeleton)
  scenarios/01-ssh-bastion/   first real scenario, 11 probes × 2 families
harness/
  README.md                   apply/probe/score contract + JSON row schema
generate/
  README.md                   C1–C4 prompts, model pinning, extraction rules
results/
  .gitkeep                    raw JSON is git-ignored; summaries are committed
scripts/
  check-env.sh                verifies the machine; --live builds the whole lab
```

### Scenario format, in one glance

| File | Contains | Written |
|---|---|---|
| `policy.yaml` | the prompt a model receives + metadata | before any model runs |
| `expected.yaml` | every probe and its required outcome per family | before any model runs |
| `expert.nft` | hand-written reference that must pass 100% | before any model runs |

Scenario 01 is a dual-stack SSH bastion with a scoped administrator network and
`policy drop` — the variant that exposes defect **C**. It has 11 probes across
two families and already declares, in `unprobed`, the two flows it does not test
and why.

---

## 10. Current state — honest

| Component | State |
|---|---|
| Topic scoped, novelty checked | **done** |
| Closest prior work read in full (SBRC 2026) | **done** |
| Written plan, 14-day sprint, related work, ethics | **done** |
| Lab topology and scenario schema | **done** |
| Scenario 01 + template + oracle + expert config | **done** (not yet executed) |
| `harness/*.py` (apply, probe, score) | **specified only — 0 lines written** |
| `generate/*.py` (model runner, RAG) | **specified only — 0 lines written** |
| WSL2 / Linux lab | **not installed — hard blocker** |
| Pilot dataset | none yet |

No result has been produced. Everything above is design plus one unexecuted
scenario. That distinction is deliberate: this document will not represent
intent as progress.

---

## 11. The two-week plan

**Mon 23 Nov → Sun 6 Dec 2026**, ~2–3 hours a day, ~35 hours total.

| Gate | When | Passes when | If it fails |
|---|---|---|---|
| **G1 — Lab works** | Tue 24 Nov | `nft` loads a ruleset inside a namespace; ping works over IPv4 **and** IPv6 across a veth pair | **Stop and fix.** Nothing downstream is meaningful. |
| **G2 — Models reachable** | Mon 30 Nov | one local Ollama model answers, plus one free-tier API key | Go local-only; one model is still a valid pilot |
| **G3 — Pilot data exists** | Thu 3 Dec | ≥6 scenarios × 3 models × C1 × 3 repeats stored as JSON | cut to 4 scenarios; keep 3 models and 3 repeats |

| Week | Work |
|---|---|
| 1 | Install WSL2 → build the lab → `check-env.sh --live` green → harness v0 → scenarios 01–03 → negative controls for defects C and D → tag `v0.1-lab` |
| 2 | Model runner → C1 runs → C2/C3 runs → analysis + two figures → tag `v0.2-pilot` → Zenodo DOI |

**Cut list, in order:** C4 repair → third model → C3 RAG → reduce to 4
scenarios. **Never cut:** the expert gate, the IPv6-disabled control, the three
repeats.

**Definition of done for the sprint:** someone else can clone the repository,
run two commands, and reproduce the pilot numbers without asking a question.

---

## 12. Ethics and safety

The lab has the smallest attack surface the project can have.

- **Host-only networking, never bridged.** A bridged adapter would receive a
  real globally routable IPv6 prefix, and a defect-D configuration would expose
  a live host to the Internet for the duration of the run. Check before every
  session: `ip -6 addr show scope global` — only `fe80::/10` and `fd00::/8` are
  acceptable. Anything in `2000::/3` means stop.
- **Snapshot or recreate before every apply.** A generated ruleset can lock the
  operator out of the machine it runs on.
- **No third-party systems.** No scanning, no testing against real routers,
  ISPs, universities or public services. No capture beyond our own lab links.
- **No human subjects, no personal data, no credentials.** Model outputs are
  synthetic text and are published verbatim, including failures.
- **Documentation ranges only:** RFC 5737 (`10.20.0.0/24`, `198.51.100.0/24`)
  and RFC 3849 (`2001:db8::/32`). No packet from this lab can be confused with
  real traffic.
- **If a vendor hardening guide is later found IPv6-incomplete,** the vendor is
  not named until disclosure completes.

---

## 13. Publication route

| Level | Target |
|---|---|
| Course | CSE 4531 Stage 4 report + viva |
| Workshop | CAMLIS · ACM ANRW · USENIX WOOT · NDSS MADWeb |
| Full | ACM IMC · USENIX Security · ACM CoNEXT |
| Regional | NSySS (Dhaka) · ICCIT |

The novel claim survives review because it is a **measurement**, not a tool: the
benchmark, the taxonomy, and the intervention breakdown are each independently
citable, and the artifact is small enough that a reviewer can re-run it.

---

## 14. What happens next

1. **Install the lab** (blocker): `wsl --install -d Ubuntu`, reboot, then
   `sudo bash scripts/check-env.sh --live`. Green means gate **G1** is passed.
2. **Write `harness/lab.py`, `apply.py`, `probe.py`, `score.py`** against the
   contract in `harness/README.md`. Run scenario 01's `expert.nft` and require
   `PASS 11/11`.
3. **Prove the oracle can fail:** hand-write one configuration exhibiting
   defect **C** and one exhibiting defect **D** in `tests/negative/`, and
   confirm the harness flags both. An oracle that cannot be made to fail has
   not been tested.
4. **Add scenarios 02 and 03,** then freeze the YAML schema.
5. **Wire the model runner,** run C1 across three models, and start the
   dataset at gate **G3**.

### Facts still needed to finalise the timeline

| Needed | Why it changes the plan |
|---|---|
| Stage 4 submission date | Compresses or expands the 6-week course timeline |
| Laptop RAM | 8 GB means one small quantised model; 16 GB means a comfortable local baseline |
| Ollama installed? | Decides whether G2 can pass on Day 8 |
| Any free-tier API key? | Decides whether the "hosted frontier model" column exists at all |

---

## 15. Key references

| Work | Venue / DOI | Why it matters here |
|---|---|---|
| Colombo & Martinello, *Framework para Verificação e Validação Experimental de Configurações de Rede Geradas por LLMs* | SBRC 2026, 814–827 · `10.5753/sbrc.2026.19857` | Closest work. Four-stage verification pipeline, IPv4-only intent. Source of the gap statement |
| Wang et al., *NetConfEval* | CoNEXT 2024 · `10.1145/3656296` | The benchmark SBRC 2026 builds on; IPv4-only tasks |
| Czyz et al., *Don't Forget to Lock the Back Door!* | NDSS 2016 | The IPv6 policy gap exists in real networks, unintentionally |
| *Where Have All the Firewalls Gone?* | arXiv `2509.04792` | 93.8M reachable IPv6 addresses; NAT was the de facto firewall |
| Jesus, Martinello, Zambon, *DETOX* | WTF 2016 | Firewall policy anomaly detection — the methodological ancestor of RQ2 |
| Diekmann et al., *Verified iptables Firewall Analysis* | IFIP Networking 2016 · Zenodo `10.5281/zenodo.804867` | Formal analysis covering both families; shows the problem is understood, not solved at generation time |
| *Can my firewall system enforce this policy?* | *Computers & Security* 2022 · `10.1016/j.cose.2022.102683` | Expressiveness differs across firewall systems; grounds the "policy vs implementation" framing |
| Anwar & Caesar, *Understanding misunderstandings* | SIGCOMM CCR 54(4), 2024 | Models produce valid syntax without network semantics |
| *Kaizen* | arXiv `2607.04058` | Compilation success ≠ behavioural correctness; precedent for differential testing |

**Citation caution.** SBRC 2026 attributes NetConfEval to *Dahlmann et al.*; the
DOI record, the artifact repository and the CoNEXT paper attribute it to **Wang
et al. (2024)**. Cite Wang et al.

**Second caution.** SBRC 2026 claims `p < 0.05` in §5 but admits "single
execution, no variance analysis" in §6. Cite the finding (100% syntax vs 80%
operational), not the p-value.
