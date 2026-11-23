# Related Work

Last verified: 23 November 2026

**How to read this table.** The "What they tested" column records what the paper's method actually executes. The "What they did not test" column records what is *absent* — which is not the same as what the abstract omits. Where a claim depends on the full text, the full text was read and is marked ✅.

---

## Closest prior work

| # | Paper | Venue / DOI | What they tested | What they did not test | Artifact |
|---|---|---|---|---|---|
| 1 | **Framework para Verificação e Validação Experimental de Configurações de Rede Geradas por LLMs** — Colombo & Martinello | SBRC 2026, pp. 814–827 · `10.5753/sbrc.2026.19857` | 4-stage pipeline (syntax → YANG conformance → semantic/DETOX → Mininet packet tests) on NetConfEval Task 1, 1,665 tasks. Found 100% syntax vs 80% operational for Claude 3.5 Sonnet. ✅ full text read | **No firewall rules. No IPv6. No dual-stack.** Intent is IPv4-only, so a config with an empty IPv6 table scores as correct | GitHub `cscolomboIA/llm-network-validation-framework` |
| 2 | **Analysis of the Capability and Training of Chat Bots in the Generation of Rules for Firewall or Intrusion Detection Systems** — Louro et al. | ARES 2024 · `10.1145/3664476.3670902` | Chatbot-generated firewall/IDS rules; fine-tuning comparison | IPv6 parity; execution-based dual-stack testing (to verify) | Claimed replication dataset — **unverified**, contact authors |
| 3 | **Parameter-Efficient Fine-Tuning of LLMs for Intrusion Detection and Firewall Rule Generation** — Zhang et al. | STM 2025 · `10.1007/978-3-032-06155-3_5` | PEFT for nftables + Snort rule generation; ~95% on 100 pairs | Success judged at rule level, not by dual-stack packet behaviour | none located |
| 4 | **MEDIotWALL** | *Sensors* 25(19):6235 · `10.3390/s25196235` | LLM suggests nftables rules from alerts, human approves | Natural-language policy; IPv6 correctness; execution parity | none |

---

## Benchmarks (all routing / repair oriented)

| # | Paper | Venue | Scope | Dataset provided |
|---|---|---|---|---|
| 5 | **NetConfEval** — Wang, Scazzariello, Farshin, Ferlin, Kostić, Chiesa | CoNEXT 2024 · `10.1145/3656296` | Requirement → formal spec, function call, routing algorithm, config generation | ✅ HuggingFace `NetConfEval/NetConfEval` (MIT, 1K–10K rows) + GitHub `RedHatResearch/conext24-NetConfEval` ★44 |
| 6 | **NetLLMBench** — Aykurt, Blenk, Kellerer | IEEE NFV-SDN 2024 · `10.1109/nfv-sdn61811.2024.10807499` | LLM config tasks in Kathara/Docker emulation | ⚠️ framework only — GitHub `tum-lkn/netllmbench` ★5, no dataset directory |
| 7 | **NetArena** | arXiv `2506.03231` | Dynamic agent benchmark, k8s / route / malt apps | ⚠️ generator only — GitHub `Froot-NetSys/NetArena` |
| 8 | **NetConfArena** | arXiv `2608.23179` | Closed-loop agents, 96 templates, 480 instances | ✅ GitHub `liujona/NetConfArena` ★10 — **all 25 visible task dirs are routing (Static/RIP/OSPF/BGP), none firewall** |
| 9 | **Cornetto** | arXiv `2604.22513` | LLM-driven network configuration **repair**, formal verification | ✅ HuggingFace `iprotogeros/cornetto-benchmark` (MIT, 4,463 downloads) + GitHub `nsg-ethz/cornetto` ★18 |

> **Citation caution.** The SBRC 2026 paper attributes NetConfEval to *Dahlmann et al. (2024)*. The DOI record, the artifact repository, and the CoNEXT paper attribute it to **Wang et al. (2024)**. Cite Wang et al.

---

## IPv6 security motivation

| # | Source | Contribution |
|---|---|---|
| 10 | **Czyz, Luckie, Allman, Bailey** — "Don't Forget to Lock the Back Door!" | NDSS 2016 | IPv4/IPv6 policy gaps in real networks; 12/12 operators confirmed unintentional |
| 11 | **"Where Have All the Firewalls Gone?"** | arXiv `2509.04792` | 93.8M reachable IPv6 addresses; 11× more HP printers than Shodan finds on all of IPv4; NAT was the de facto firewall |
| 12 | **RFC 9099** | IETF 2021 | Operational security considerations for IPv6 networks |
| 13 | **NIST SP 800-119** | 2010 | Guidelines for secure IPv6 deployment |

---

## Rule-anomaly detection (methodological ancestor)

| # | Source | Relevance |
|---|---|---|
| 14 | **DETOX** — Jesus, Martinello, Zambon, WTF 2016 | Inconsistency detection in real firewall policies (shadowing, redundancy, correlation). Directly relevant to the static-heuristic half of RQ2 |
| 15 | **Verified iptables Firewall Analysis** — Diekmann et al., IFIP Networking 2016 · Zenodo `10.5281/zenodo.804867` | Isabelle/HOL formal analysis covering IPv4 and IPv6 |
| 16 | **Can my firewall system enforce this policy?** — *Computers & Security* 2022 · `10.1016/j.cose.2022.102683` | Formal differences in expressiveness across iptables, ipfw, pf |

---

## Behavioural-correctness precedent

| # | Source | Why it matters here |
|---|---|---|
| 17 | **Kaizen** — arXiv `2607.04058` | Compilation success ≠ behavioural correctness; metamorphic + differential testing for LLM-translated code |
| 18 | **Anwar & Caesar**, "Understanding misunderstandings: Evaluating LLMs on networking questions", ACM SIGCOMM CCR 54(4), 2024 | Models can produce valid syntax without understanding network semantics |

---

## Public firewall configuration data

| Source | Size | Scope | License |
|---|---|---|---|
| **iptables4-configuration-collection** — Zenodo `10.5281/zenodo.12772748` | 243 KB zip | Real-world iptables configs, harmonised. **Explicitly IPv4 only** | check record |
| **Iptables_Semantics** test rulesets — Zenodo `10.5281/zenodo.804867` | tool + tests | Formal-analysis test corpus | GPL-family |

> Even the community-curated public collection is scoped to IPv4. That is the field's default assumption, stated by the people who built the corpus.

---

## The gap in one paragraph

Colombo & Martinello verify that a generated configuration achieves its stated intent, and correctly show that syntax is a poor proxy for behaviour. But the intent they verify is expressed in one address family. On Linux, a configuration can satisfy that intent completely and still leave the other family either wide open or entirely unreachable, because address matches are family-scoped even inside an `nftables` `inet` table. No published benchmark contains dual-stack firewall scenarios, and no public dataset of firewall configurations carries IPv6 parity annotations. We measure that axis, classify its failure mechanisms, and test whether prompting, retrieval, or repair closes it.
