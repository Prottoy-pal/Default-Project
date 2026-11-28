# Scenarios — the benchmark

A **scenario** is one policy, expressed twice:

1. as a natural-language **prompt** a model can receive, and
2. as a machine-checkable **oracle** describing what the running firewall must do.

A scenario is only valid if a hand-written reference configuration passes its
oracle 100%. That reference is `expert.nft`, and it is a gate, not an example.

---

## Directory layout

```
bench/
├── topology.yaml              addresses, links, services — one definition
└── scenarios/
    ├── _template/             copy this to start a new scenario
    │   ├── policy.yaml
    │   ├── expected.yaml
    │   └── expert.nft
    └── 01-ssh-bastion/
        ├── policy.yaml        what the model sees + scenario metadata
        ├── expected.yaml      what the harness checks
        └── expert.nft         hand-written reference (must pass 100%)
```

Nothing in a scenario file may contain an IP address that is not also in
`bench/topology.yaml`.

---

## The three files

### `policy.yaml` — input side

| Field | Meaning |
|---|---|
| `id` | Must equal the directory name. |
| `order` | 1-based position in the benchmark. |
| `family` | Which of the eight service families (see below). |
| `variant` | Which of the four design variants (see below). |
| `dialect` | `nftables` (core), or `iptables` / `ufw` (extension). |
| `prompt` | **The only text a model receives** in condition C1. |
| `services` | Ports the lab must have a listener on for this scenario. |
| `targets` | Defect classes (A–E) this scenario is *capable* of exposing. |

**Eight families:** `ssh-bastion`, `web-server`, `db-server`, `dns-resolver`,
`container-host`, `forwarding-gateway`, `monitoring-host`, `bastion-plus-web`.

**Four variants** — a 2 × 2 factorial. This is what makes attribution possible:
a failure can be traced to a design feature instead of to a hand-written
scenario's quirks.

| Variant | Source scope | Default policy | Expected defect if the model is family-blind |
|---|---|---|---|
| `any-default-drop` | any | drop | over-block on v6 (nothing is allowed) |
| `scoped-default-drop` | scoped | drop | **C** — over-block on v6 |
| `any-default-accept` | any | accept | v6 stays open where v4 is also open |
| `scoped-default-accept` | scoped | accept | **D** — fail-open on v6 |

### `expected.yaml` — check side

```yaml
probes:
  - id: ssh-from-admin
    tier: specified
    proto: tcp                        # tcp | udp | icmp-echo | icmp6-nd
    src: admin                        # a zone from topology.yaml, or `loopback`
    dst: dut-admin                    # dut-admin | dut-wan | a zone | `loopback`
    dport: 22                         # tcp/udp only; a scalar or a list
    expect: { ipv4: allow, ipv6: allow }
    rationale: "One sentence: why this outcome is what the policy requires."
```

`expect` may name only one family. A probe that omits `ipv6` is not scored on
IPv6 — use this only when the policy genuinely has nothing to say about that
family, never to make a result look better.

### Two tiers

| Tier | Definition | Question answered |
|---|---|---|
| **specified** | A flow the prompt explicitly asks about | Did the model implement what it was told? |
| **silent** | A flow implied by a competent implementation but never stated | Did the model implement what it should have known? |

A configuration that passes every *specified* probe and fails a *silent* one
is not a near miss. It is the finding: the policy reads as satisfied while
the host is not actually protected.

Every probe carries a `rationale`. If you cannot write one sentence justifying
the expected outcome, the probe is a guess and should be deleted.

### `unprobed` — what the oracle does not test

Declared explicitly, never omitted:

```yaml
unprobed:
  - id: stateful-return-traffic
    reason: >-
      Needs a conntrack-aware probe whose verdict is confounded with the
      output chain. Deferred, and named in the threats-to-validity section.
```

---

## Defect classes the oracle must be able to see

| Class | Construction | Effect on the other family | Where it shows up |
|---|---|---|---|
| **A** | `table ip` only; no `ip6`, no `inet` | v6 traverses no chain — unfiltered | v6 drop-probes fail, v6 allow-probes pass |
| **B** | `table ip` + `table ip6`, v6 chain empty or `policy accept` | same, but looks deliberate | v6 drop-probes fail, v6 allow-probes pass |
| **C** | `inet` + `policy drop` + `ip saddr … accept` | v6 admin traffic blocked | `scoped-*` variants, allow-probes |
| **D** | `inet` + `policy accept` + `ip saddr … drop` | v6 attack traffic never dropped | `scoped-*` variants, drop-probes |
| **E** | `icmp type` where `icmpv6 type` is needed; blanket `icmpv6 drop` | ND dies, IPv6 non-functional | `icmp6-nd` probe, `resolution` field |

A and B are fail-open like D, and execution alone cannot tell them apart from
it: in all three the second family accepts what the policy refuses. What
separates them is structure — no IPv6 table at all (A), a split table whose v6
chain filters nothing (B), or an `inet` table whose default policy is accept
(D). `score.py` therefore decides A/B from the configuration text and C/D from
the probes.

A scenario whose `targets` list includes a class but whose `expert.nft` cannot
distinguish that class from a correct configuration is mis-specified. Prove it
with a negative control in `tests/negative/`.

---

## Authoring rules

1. **Write `expected.yaml` before prompting any model.** Once written, it may
   change only for a documented reason in the commit message.
2. **Never edit the oracle to match a model's output.** That is the one
   unrecoverable mistake in this project.
3. **The prompt states intent, not implementation.** Say *what must be
   permitted*; never say *use `inet`* or *write an `ip6` rule*. Naming the
   construct would measure instruction-following, not knowledge.
4. **State both families' addresses in the prompt.** If the policy scopes a
   source network, give its IPv4 *and* IPv6 prefix. Otherwise a failure is a
   guess about an unstated address, not a defect.
5. **One idea per scenario.** If a scenario needs two sentences to describe
   its purpose, split it.
6. **`expert.nft` must pass 100%, in both families, before the scenario is
   committed.** If it does not, the oracle is wrong.

---

## Checklist for a new scenario

```
[ ] Directory name == policy.yaml id
[ ] family and variant are from the fixed enumerations
[ ] prompt gives both families' addresses where a source is scoped
[ ] prompt never names an nftables construct
[ ] every probe has a one-sentence rationale
[ ] every probe's src/dst exists in bench/topology.yaml
[ ] services block matches the ports the probes touch
[ ] expert.nft passes 100%
[ ] a deliberately broken config in tests/negative/ is caught by this oracle
```
