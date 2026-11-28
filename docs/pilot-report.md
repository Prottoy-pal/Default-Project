# Pilot report — 28 November 2026

A first, small run to make sure the pipeline produces a result worth reading,
before spending the time on the full matrix. It did — and the result is a
finding about the *instrument* as much as about the model.

## Method

- **Model:** `qwen2.5-coder:7b`, run locally through Ollama on CPU.
- **Sampling:** temperature 0, `top_p` 1.0, fixed seed. Deterministic.
- **Conditions:** C1 (plain prompt) and C2 (plain prompt plus an explicit
  "enforce this policy for both IPv4 and IPv6 traffic" sentence).
- **Scenarios:** the eight committed scenarios (01–08), one repeat each.
- **16 cells total**, each scored by executing the generated ruleset in the lab
  against a hand-written oracle.

## Results

| Condition | Cells | Loaded | Load-failure | Parity (over loaded) | Defects |
|---|---|---|---|---|---|
| C1 | 8 | 1 | 87.5% [52.9, 97.8] | 0% (0/1) | E ×1 |
| C2 | 8 | 2 | 75.0% [40.9, 92.9] | 0% (0/2) | E ×2 |

Intervals are Wilson 95%.

Two facts dominate the table.

### 1. The model mostly could not produce a loadable ruleset (13 of 16 cells)

Thirteen of sixteen rulesets were rejected by nftables. The errors, in
frequency order:

- **12 × a shell-escaped semicolon.** The model wrote `priority 0 \; policy
  drop` — a `\;` it copied from `nft` *command-line* examples, where the
  backslash is needed to survive the shell. Inside a ruleset file it is a
  syntax error.
- **1 × mixing address families in one rule.** `ip saddr … ip6 saddr …` in a
  single statement, which nftables rejects ("conflicting network layer
  protocols").

Both are recorded as class **S** (load failure), kept separate from the five
behavioural classes, and excluded from their denominators.

### 2. Every cell that *did* load broke IPv6 by dropping neighbour discovery (3 of 3)

The three loadable rulesets were otherwise family-symmetric and correct: they
passed 36/37, 40/41 and 40/41 probes, with IPv4 fully correct and only the
`ipv6-neighbour-discovery` probe failing. Under a `policy drop` table with no
`icmpv6 type nd-* accept`, IPv6 discovery dies — class **E**.

That this reads as E *alone* is the direct result of the neighbour-pinning fix
made earlier in the day: before it, the same ruleset would have been reported
as C+E, with the dead link masquerading as an over-block.

### 3. C and D did not appear, and C2 did not help

The two classes this project set out to study — a scoped `ip saddr` inside an
`inet` table — never surfaced, and the explicit dual-stack instruction (C2)
made no meaningful difference (6/8 vs 7/8 load failures, and the loaded cells
still broke IPv6).

The reason is worth stating plainly: **the syntax-failure rate censors the
signal.** Several rulesets began with `table ip` (IPv4-only) or carried
family-scoped matches, which *would* have been classes A, C or D — but they
failed to load first, so no behaviour was observed and they are class S. A
benchmark that folded S into the behavioural classes would have reported a
phantom C/D prevalence; this one does not.

### 4. C4 repair made it worse

Because syntax failure dominates, the natural test is C4: feed the error back
and ask for a correction. The result was unambiguous, and negative.

| Condition | Loaded after | What the repair did |
|---|---|---|
| C1 (no repair) | 1 / 8 | — |
| C4 (one repair round) | 0 / 8 | broke the one loadable ruleset, fixed none of the seven syntax errors |

In seven cells the model re-emitted the **same** `\;` after being shown the
exact parse error, and in the one cell that had loaded (scenario 03), it was
asked to fix the missing neighbour discovery and instead produced a new error —
"Could not parse ICMPv6 type expression" — turning a working-but-incomplete
ruleset into a broken one.

This is a finding about the model, not a reason to drop C4: a 7B model that
cannot self-correct its own lexer errors cannot be repaired by pointing at
them. The intervention may still matter for a stronger model whose first
attempt loads and fails behaviourally — which is the case the intervention was
originally designed for.

## What this means for the design

- **S must stay its own column.** The literature reports near-perfect syntax
  for frontier models; a local 7B model sits at the opposite end. The two are
  different findings and must not be averaged.
- **Repair cannot rescue a model that cannot parse.** C4's value is conditional
  on the first attempt loading; with this model it never gets a chance.
- **The other model slots matter more than the intervention.** C and D are
  invisible when nothing loads, and repair does not unblock that. A stronger
  model is the lever.

## Limitations

- One model, one repeat, eight scenarios. No conclusion about *prevalence* can
  survive this sample; this is a pipeline check, not an estimate.
- Local CPU inference at 7B is a floor, not a ceiling, for what these models
  can do.
- The three loaded cells all shared one failure shape (E); C and D remain
  unobserved, not absent.

## Next steps

1. Add the second and third model slots. The pilot says the lever is model
   strength, not prompting or repair.
2. Reach the full matrix (12 scenarios × conditions × repeats) for Gate D once
   a model that loads reliably is in place.
3. Keep C4 for the case it was built for: a model whose first attempt loads and
   fails behaviourally.
