# Half a Firewall

**Execution-based evaluation of IPv6 policy coverage in LLM-generated Linux firewall configurations**

`Status: Stage 1 — proposal + pilot` · `Cost: $0` · `Lab: local, isolated` · `License: MIT`

**New here?** [docs/context.md](docs/context.md) is the whole project in one file — problem, gap, design, current state, next steps.

---

## In one sentence

We ask whether firewall rules written by an AI actually protect **both** IPv4 and IPv6 — and we answer it by sending real packets, not by reading the configuration.

---

## Plain-language summary

A firewall is a guard at the door of a computer. It checks every connection and decides: allow or block.

Computers today speak two address systems at once — the old **IPv4** and the newer **IPv6**. A machine with both is called **dual-stack**. A firewall has to guard both doors. If the guard locks the front door and forgets the back, the house still looks secure from the street.

People increasingly ask AI assistants to write their firewall rules. This project tests whether the rules an AI produces actually enforce the requested policy on **both** protocols when the configuration is executed.

**The subtle part:** on Linux, a single `nftables` `inet` table is widely assumed to protect both protocols automatically. It does not. Address matches such as `ip saddr` apply to **IPv4 only**, even inside an `inet` table. A configuration can therefore look dual-stack, load cleanly, pass every syntax check — and silently fail the policy on IPv6.

> **If you read only one line:** a firewall can lock the front door and leave the back door open, and a configuration that loads cleanly will not tell you which one it did. On Linux, `ip saddr` inside an `inet` table is exactly that mistake — it matches IPv4 and silently says nothing about IPv6.

---

## Why this matters

| Evidence | What it shows |
|---|---|
| Colombo & Martinello, **SBRC 2026** | Claude 3.5 Sonnet scored **100% on syntax** but only **80%** operational on a reachability policy — a 20-point false positive |
| Czyz et al., **NDSS 2016** | Real networks enforce weaker policy on IPv6 than IPv4; all 12 contacted operators confirmed the extra openness was unintentional |
| HuggingFace search, Nov 2026 | `iptables` → **0 datasets**, `nftables` → **0**, `firewall rules` → **0** |
| Zenodo, 2024 | The community-maintained iptables collection is explicitly scoped to **IPv4 networks** |

The tooling people reach for during the IPv6 transition reproduces the IPv4-only mental model that created the problem.

---

## Research questions

| ID | Question |
|---|---|
| **RQ1 — Prevalence** | Under a plain prompt with an explicitly dual-stack policy, what proportion of generated configurations fail to enforce the policy on at least one family — and how does IPv4 failure compare with IPv6 failure? |
| **RQ2 — Mechanism** | Which construction patterns predict failure (family omission, split tables, family-scoped matches, default-policy choice, ICMPv6 handling)? Can any static heuristic predict execution outcomes? |
| **RQ3 — Intervention** | Do explicit dual-stack instruction, documentation-grounded RAG, or execution-feedback repair reduce failure — and **which defect classes respond to which intervention**? |

**Pre-registered expectations**

- **H1** — IPv6 enforcement will be weaker than IPv4 with plain prompting.
- **H2** — Failure classes differ by dialect: `table ip` omission produces fail-open; family-scoped matches inside `inet` produce over-block or fail-open depending on the default policy.
- **H3** — RAG fixes defects the documentation mentions (family omission) and not the ones it does not (family-scoped matches inside `inet`).

---

## How it works

```
   Natural-language policy
            │
            ▼
   ┌──────────────────┐
   │  LLM generates   │   ← 3 models × 3 conditions × 3 repeats
   │  nftables config │
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │  Apply in lab    │   isolated netns pair, host-only, no bridge
   │  (snapshot reset)│
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │  Send real probes│   TCP / UDP / ICMP over IPv4 *and* IPv6
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │  Score vs.       │   expected.yaml is written BEFORE any model runs
   │  ground truth    │   and expert.nft must pass 100%
   └──────────────────┘
```

---

## Defect taxonomy

| # | Mechanism | Effect | Direction |
|---|---|---|---|
| **A** | `table ip` only; no `ip6` table, no `inet` | IPv6 traverses no chain → unfiltered | **fail-open** |
| **B** | `table ip` + `table ip6`, v6 chain empty or `policy accept` | same, but looks deliberate | **fail-open** |
| **C** | `inet` + `policy drop` + `ip saddr … accept` | v6 admin/services unreachable | over-block |
| **D** | `inet` + `policy accept` + `ip saddr … drop` | v6 attack traffic never dropped | **fail-open** |
| **E** | `icmp type` where `icmpv6 type` is needed; or blanket `icmpv6 drop` | neighbour discovery dies → IPv6 non-functional | over-block |

Defects **C** and **D** are the novel ones. They survive every rule-counting check.

---

## What we measure

| Metric | Definition |
|---|---|
| Syntax validity | Parses and applies without error |
| Load success | Firewall accepts the ruleset |
| IPv4 / IPv6 correctness | Probes match `expected.yaml` for that family |
| **Parity** | Both families correct |
| Fail-open count | Traffic that should be blocked but passes |
| Over-block count | Traffic that should be allowed but is blocked |
| **Exposure delta** | Reachable services on IPv6 minus IPv4, from an untrusted zone |
| Static-check agreement | How often a rule-counting heuristic predicts real behaviour |

---

## Repository layout

```
.
├── README.md                  ← you are here
├── docs/
│   ├── context.md             the whole project in one file — start here
│   ├── pipeline.md            every task, with time, difficulty and gates
│   ├── research-plan.md       full design, hypotheses, metrics, threats
│   ├── sprint-01.md           2-week work plan (23 Nov – 6 Dec 2026)
│   ├── related-work.md        literature table, incl. SBRC 2026
│   └── ethics.md              safety rules for the lab
├── bench/
│   ├── topology.yaml          addresses and links — defined once, used everywhere
│   └── scenarios/
│       ├── README.md          the scenario format, and the rules for writing one
│       ├── _template/         copy this to start a new scenario
│       └── 01-ssh-bastion/    policy.yaml + expected.yaml + expert.nft
├── harness/                   apply / probe / score  (built in Sprint 1)
├── generate/                  prompts + model runner (built in Sprint 1)
├── results/                   raw JSON, git-ignored except .gitkeep
└── scripts/
    └── check-env.sh           verifies your lab can run the benchmark
```

---

## Anatomy of a scenario

Every scenario is three files, and the order in which they were written is the
whole method:

| File | Contains | Written |
|---|---|---|
| `policy.yaml` | the prompt a model receives, plus metadata | before any model runs |
| `expected.yaml` | every probe and its required outcome, per family | before any model runs |
| `expert.nft` | a hand-written reference implementation | before any model runs |

`expert.nft` must pass **100%** of `expected.yaml` — both families — before a
single model is prompted. If it fails, the test is wrong, not the firewall.

Full schema and authoring rules: [bench/scenarios/README.md](bench/scenarios/README.md).

---

## Quick start

**Requirements:** Windows 10/11 with WSL2 Ubuntu, or any Linux box. No GPU. No cloud account.

```bash
# 1. Verify your lab
bash scripts/check-env.sh

# 2. Run one scenario against its expert configuration
#    (this must print PASS before you ever prompt a model)
bash harness/run.sh bench/scenarios/01-ssh-bastion
```

If `check-env.sh` fails, fix the lab first. A broken harness makes every result meaningless.

> **Step 2 is not runnable yet.** `harness/run.sh` arrives with the harness on
> Sprint 1, days 3–4. Step 1 works today. This line exists so that no reader
> mistakes a plan for a working tool.

---

## Plan and pipeline

**[docs/pipeline.md](docs/pipeline.md)** is the master view: every task with an
ID, a time estimate, a difficulty from 1 (mechanical) to 4 (open-ended), its
dependencies, and the gate it must pass. 121 hours, six gates, one cut ladder.

**[docs/sprint-01.md](docs/sprint-01.md)** is the first two weeks in daily
detail. When the two disagree, `pipeline.md` is newer.

---

## Status

- [x] Topic selected and scoped
- [x] Preliminary novelty check (arXiv, OpenAlex, GitHub, HuggingFace, Zenodo)
- [x] Closest prior work read (SBRC 2026, full text)
- [ ] **Sprint 1** — lab + 6 scenarios + pilot run
- [ ] Benchmark frozen at 32 scenarios
- [ ] Full generation runs (C1–C3)
- [ ] Analysis, figures, paper draft
- [ ] Zenodo release with DOI

---

## Ethics and safety

All work happens inside an isolated virtual lab on one machine. No third-party systems, no scanning, no real networks, no human subjects. **The lab network adapter must be host-only — never bridged.** See [docs/ethics.md](docs/ethics.md).

---

## Citing

```bibtex
@misc{halffirewall2026,
  title  = {Half a Firewall: Execution-Based Evaluation of IPv6 Policy
            Coverage in LLM-Generated Linux Firewall Configurations},
  author = {Prottoy Pal},
  year   = {2026},
  note   = {Research proposal, CSE 4531 Computer Security, UIU},
  url    = {https://github.com/Prottoy-pal/Default-Project}
}
```

---

## License

Code and benchmark: **MIT**. See [LICENSE](LICENSE).
